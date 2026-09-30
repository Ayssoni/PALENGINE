"""SQLite storage for multiple students: identity, per-concept BKT mastery, and the attempt log."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "pal_advanced.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    grade       INTEGER NOT NULL,
    school      TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS concept_mastery (
    student_id  INTEGER NOT NULL,
    concept_id  TEXT NOT NULL,
    p_mastery   REAL NOT NULL,
    attempts    INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (student_id, concept_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
CREATE TABLE IF NOT EXISTS attempts (
    attempt_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       INTEGER NOT NULL,
    question_id      TEXT NOT NULL,
    concept_id       TEXT NOT NULL,
    chosen_option    TEXT NOT NULL,
    is_correct       INTEGER NOT NULL,
    misconception_id TEXT,
    is_review        INTEGER NOT NULL DEFAULT 0,
    time_taken_sec   REAL,
    p_mastery_before REAL,
    p_mastery_after  REAL,
    attempted_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
CREATE INDEX IF NOT EXISTS idx_attempts_student ON attempts(student_id);
CREATE INDEX IF NOT EXISTS idx_attempts_concept ON attempts(student_id, concept_id);
"""


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db():
    con = connect()
    con.executescript(SCHEMA)
    con.commit()
    con.close()


def reset_db():
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()


# ---------------------------------------------------------------- students
def create_student(name, grade, school=None):
    con = connect()
    cur = con.execute("INSERT INTO students (name, grade, school) VALUES (?,?,?)", (name, grade, school))
    con.commit()
    sid = cur.lastrowid
    con.close()
    return sid


def get_student(student_id):
    con = connect()
    r = con.execute("SELECT * FROM students WHERE student_id=?", (student_id,)).fetchone()
    con.close()
    return dict(r) if r else None


def list_students(grade=None):
    con = connect()
    if grade is None:
        rows = [dict(r) for r in con.execute("SELECT * FROM students ORDER BY student_id")]
    else:
        rows = [dict(r) for r in con.execute("SELECT * FROM students WHERE grade=? ORDER BY student_id", (grade,))]
    con.close()
    return rows


# ---------------------------------------------------------------- mastery
def get_mastery_map(student_id, default_p):
    """concept_id -> p_mastery, defaulting concepts never attempted to `default_p`."""
    con = connect()
    rows = con.execute("SELECT concept_id, p_mastery FROM concept_mastery WHERE student_id=?", (student_id,)).fetchall()
    con.close()
    return {r["concept_id"]: r["p_mastery"] for r in rows}, default_p


def get_concept_mastery(student_id, concept_id, default_p):
    con = connect()
    r = con.execute("SELECT p_mastery FROM concept_mastery WHERE student_id=? AND concept_id=?",
                    (student_id, concept_id)).fetchone()
    con.close()
    return r["p_mastery"] if r else default_p


def set_concept_mastery(student_id, concept_id, p_mastery):
    con = connect()
    con.execute("""INSERT INTO concept_mastery (student_id, concept_id, p_mastery, attempts, updated_at)
                   VALUES (?,?,?,1,CURRENT_TIMESTAMP)
                   ON CONFLICT(student_id, concept_id)
                   DO UPDATE SET p_mastery=excluded.p_mastery, attempts=attempts+1, updated_at=CURRENT_TIMESTAMP""",
               (student_id, concept_id, p_mastery))
    con.commit()
    con.close()


# ---------------------------------------------------------------- attempts
def log_attempt(student_id, question_id, concept_id, chosen_option, is_correct,
                misconception_id, is_review, time_taken, p_before, p_after):
    con = connect()
    con.execute("""INSERT INTO attempts (student_id, question_id, concept_id, chosen_option, is_correct,
                   misconception_id, is_review, time_taken_sec, p_mastery_before, p_mastery_after)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
               (student_id, question_id, concept_id, chosen_option, int(is_correct),
                misconception_id, int(is_review), time_taken, p_before, p_after))
    con.commit()
    con.close()


def student_attempts(student_id):
    con = connect()
    rows = [dict(r) for r in con.execute(
        "SELECT * FROM attempts WHERE student_id=? ORDER BY attempt_id", (student_id,))]
    con.close()
    return rows


def asked_questions(student_id):
    con = connect()
    rows = {r[0] for r in con.execute("SELECT DISTINCT question_id FROM attempts WHERE student_id=?", (student_id,))}
    con.close()
    return rows


def recent_misconception_run(student_id, concept_id, misconception_id, window=6):
    """How many times this misconception was hit among the student's last `window` attempts
    on this concept, counting back until a correct answer on this concept is seen (a correct
    answer 'clears' the streak). Used to confirm a repeated, not one-off, mistake."""
    con = connect()
    rows = con.execute("""SELECT is_correct, misconception_id FROM attempts
                          WHERE student_id=? AND concept_id=? ORDER BY attempt_id DESC LIMIT ?""",
                       (student_id, concept_id, window)).fetchall()
    con.close()
    count = 0
    for r in rows:
        if r["is_correct"]:
            break
        if r["misconception_id"] == misconception_id:
            count += 1
    return count


def all_attempts(grade=None):
    con = connect()
    if grade is None:
        q = """SELECT a.*, s.name AS student_name FROM attempts a JOIN students s ON s.student_id = a.student_id
               ORDER BY a.attempt_id"""
        rows = [dict(r) for r in con.execute(q)]
    else:
        q = """SELECT a.*, s.name AS student_name FROM attempts a JOIN students s ON s.student_id = a.student_id
               WHERE s.grade=? ORDER BY a.attempt_id"""
        rows = [dict(r) for r in con.execute(q, (grade,))]
    con.close()
    return rows
