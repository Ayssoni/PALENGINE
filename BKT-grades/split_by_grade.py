#!/usr/bin/env python3
"""
Splits the 100-question fractions bank (pal_fractions.db) into grade-wise datasets,
following a standard progression:

  Grade 6: fraction meaning, equivalence, simplifying, comparing, like-fraction add/sub,
           fraction of a quantity, ordering                       -> the foundations
  Grade 7: unlike-fraction add/sub, mixed numbers, multiplying, dividing fractions
                                                                    -> full arithmetic
  Grade 8: word problems combining several operations               -> applied use

This mapping is a curriculum judgement call (based on the typical NCERT sequence), not
derived from data. Adjust GRADE_OF_SUBTOPIC below to match your actual syllabus/textbook.

Outputs (in this folder):
  grade6_questions.csv, grade7_questions.csv, grade8_questions.csv   - one row per option
  all_grades_questions.csv                                          - same, with a Grade column
  grade6.db, grade7.db, grade8.db                                   - SQLite, one per grade
  combined.db                                                       - all grades, with a
                                                                       'grade' column on questions
"""
import csv
import os
import sqlite3

SRC = "/mnt/user-data/outputs/pal_fractions.db"

GRADE_OF_SUBTOPIC = {
    # Grade 6: what a fraction is, and the basic toolkit
    "Fraction as part of a whole": 6,
    "Numerator and denominator": 6,
    "Equal parts": 6,
    "Fractions on a number line": 6,
    "Comparing unit fractions": 6,
    "Equivalent fractions": 6,
    "Simplifying fractions": 6,
    "Comparing fractions with the same numerator": 6,
    "Adding like fractions": 6,
    "Subtracting like fractions": 6,
    "Fraction of a quantity": 6,
    "Whole, part and remainder": 6,
    "Comparing unlike fractions": 6,
    "Ordering fractions": 6,
    # Grade 7: full arithmetic with fractions
    "Adding unlike fractions": 7,
    "Subtracting unlike fractions": 7,
    "Mixed numbers and improper fractions": 7,
    "Adding unlike fractions (answer above 1)": 7,
    "Subtracting mixed numbers": 7,
    "Multiplying fractions": 7,
    "Dividing fractions": 7,
    "Dividing a whole number by a fraction": 7,
    # Grade 8: applying fractions in multi-step word problems
    "Fraction word problems": 8,
    "Mixed number word problems": 8,
}

COLS = ["grade", "question_id", "subtopic", "difficulty", "question_text", "correct_option",
        "explanation", "option_label", "option_text", "misconception_id", "feedback_text"]


def load_rows():
    con = sqlite3.connect(SRC)
    con.row_factory = sqlite3.Row
    rows = []
    for r in con.execute("""SELECT o.question_id, q.subtopic, q.difficulty, q.question_text,
                                   q.correct_option, q.explanation, o.option_label, o.option_text,
                                   o.misconception_id, o.feedback_text
                            FROM options o JOIN questions q ON q.question_id = o.question_id
                            ORDER BY q.question_id, o.option_label"""):
        d = dict(r)
        if d["subtopic"] not in GRADE_OF_SUBTOPIC:
            raise ValueError(f"No grade mapping for subtopic: {d['subtopic']}")
        d["grade"] = GRADE_OF_SUBTOPIC[d["subtopic"]]
        rows.append(d)
    misconceptions = {r["misconception_id"]: dict(r) for r in con.execute("SELECT * FROM misconceptions")}
    con.close()
    return rows, misconceptions


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows({k: r[k] for k in COLS} for r in rows)


SCHEMA = """
CREATE TABLE misconceptions (misconception_id TEXT PRIMARY KEY, description TEXT NOT NULL, remedy_text TEXT);
CREATE TABLE questions (question_id TEXT PRIMARY KEY, grade INTEGER NOT NULL, subtopic TEXT NOT NULL,
    question_text TEXT NOT NULL, difficulty INTEGER NOT NULL, correct_option TEXT NOT NULL, explanation TEXT NOT NULL);
CREATE TABLE options (question_id TEXT NOT NULL, option_label TEXT NOT NULL, option_text TEXT NOT NULL,
    misconception_id TEXT, feedback_text TEXT, PRIMARY KEY (question_id, option_label),
    FOREIGN KEY (question_id) REFERENCES questions(question_id),
    FOREIGN KEY (misconception_id) REFERENCES misconceptions(misconception_id));
"""


def write_db(path, rows, misconceptions, with_grade_column=True):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    schema = SCHEMA if with_grade_column else SCHEMA.replace("grade INTEGER NOT NULL, ", "")
    con.executescript(schema)

    by_q = {}
    for r in rows:
        by_q.setdefault(r["question_id"], {"grade": r["grade"], "subtopic": r["subtopic"],
                                           "question_text": r["question_text"], "difficulty": r["difficulty"],
                                           "correct_option": r["correct_option"], "explanation": r["explanation"]})
    for qid, q in by_q.items():
        if with_grade_column:
            con.execute("INSERT INTO questions VALUES (?,?,?,?,?,?,?)",
                       (qid, q["grade"], q["subtopic"], q["question_text"], q["difficulty"],
                        q["correct_option"], q["explanation"]))
        else:
            con.execute("INSERT INTO questions VALUES (?,?,?,?,?,?)",
                       (qid, q["subtopic"], q["question_text"], q["difficulty"],
                        q["correct_option"], q["explanation"]))
    for r in rows:
        con.execute("INSERT OR IGNORE INTO options VALUES (?,?,?,?,?)",
                   (r["question_id"], r["option_label"], r["option_text"],
                    r["misconception_id"] or None, r["feedback_text"] or None))
    used_mids = {r["misconception_id"] for r in rows if r["misconception_id"]}
    for mid in used_mids:
        m = misconceptions[mid]
        con.execute("INSERT INTO misconceptions VALUES (?,?,?)", (mid, m["description"], m["remedy_text"]))
    con.commit()
    con.close()


def main():
    rows, misconceptions = load_rows()
    all_qids = sorted({r["question_id"] for r in rows})
    print(f"Total questions loaded: {len(all_qids)}")

    write_csv("all_grades_questions.csv", rows)
    write_db("combined.db", rows, misconceptions, with_grade_column=True)

    for g in (6, 7, 8):
        g_rows = [r for r in rows if r["grade"] == g]
        write_csv(f"grade{g}_questions.csv", g_rows)
        write_db(f"grade{g}.db", g_rows, misconceptions, with_grade_column=False)
        qids = {r["question_id"] for r in g_rows}
        subtopics = sorted({r["subtopic"] for r in g_rows})
        mids = {r["misconception_id"] for r in g_rows if r["misconception_id"]}
        print(f"\nGrade {g}: {len(qids)} questions, {len(subtopics)} subtopics, {len(mids)} misconceptions")
        for s in subtopics:
            n = len({r["question_id"] for r in g_rows if r["subtopic"] == s})
            print(f"   - {s} ({n})")


if __name__ == "__main__":
    main()
