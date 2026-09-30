"""
PAL backend API - BKT-driven, grade-aware (grades 6, 7, 8).

Each grade has its own content database (data/grade{N}.db) and its own concept subgraph
(config.concepts.get_grade_concepts(N)). A student belongs to exactly one grade; every
endpoint about a student routes through THAT grade's Content and SelectionEngine, so a
grade-6 student is never served a grade-7 question, and mastery/prerequisites never mix
across grades.

Run:  uvicorn pal.main:app --reload --port 8000
Docs: http://127.0.0.1:8000/docs
"""
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from config.concepts import GRADES, get_grade_concepts, topo_order
from pal import bkt, db, report
from pal.content import Content, DATA_DIR
from pal.selection import SelectionEngine

app = FastAPI(title="PAL Fractions API (grade-aware)", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db.init_db()

# One Content + SelectionEngine per grade, built once at startup.
GRADE_CONCEPTS = {g: get_grade_concepts(g) for g in GRADES}
CONTENT = {g: Content(DATA_DIR / f"grade{g}.db", concepts=GRADE_CONCEPTS[g]) for g in GRADES}
ENGINES = {g: SelectionEngine(CONTENT[g], GRADE_CONCEPTS[g]) for g in GRADES}


class NewStudent(BaseModel):
    name: str
    grade: int
    school: Optional[str] = None

    @field_validator("grade")
    @classmethod
    def grade_supported(cls, v):
        if v not in GRADES:
            raise ValueError(f"grade must be one of {GRADES}")
        return v


class AnswerIn(BaseModel):
    question_id: str
    option_label: str
    is_review: bool = False
    time_taken_sec: Optional[float] = None


def _question_out(q):
    return {"question_id": q["question_id"], "subtopic": q["subtopic"], "concept_id": q["concept_id"],
            "difficulty": q["difficulty"], "question_text": q["question_text"],
            "options": [{"label": o["label"], "text": o["text"]} for o in q["options"]]}


def _require_student(student_id: int):
    s = db.get_student(student_id)
    if not s:
        raise HTTPException(404, f"No student with id {student_id}")
    return s


def _engine_for(student):
    return ENGINES[student["grade"]], CONTENT[student["grade"]], GRADE_CONCEPTS[student["grade"]]


@app.get("/health")
def health():
    return {"status": "ok", "grades": list(GRADES),
            "questions_by_grade": {g: len(CONTENT[g].questions) for g in GRADES},
            "concepts_by_grade": {g: len(GRADE_CONCEPTS[g]) for g in GRADES}}


@app.get("/grades")
def list_grades():
    return {g: {"n_concepts": len(GRADE_CONCEPTS[g]), "n_questions": len(CONTENT[g].questions)} for g in GRADES}


@app.get("/grades/{grade}/concepts")
def grade_concepts(grade: int):
    if grade not in GRADES:
        raise HTTPException(404, f"grade must be one of {GRADES}")
    return {"grade": grade, "order": topo_order(GRADE_CONCEPTS[grade]), "concepts": GRADE_CONCEPTS[grade]}


@app.post("/students")
def create_student(body: NewStudent):
    sid = db.create_student(body.name, body.grade, body.school)
    return {"student_id": sid, "name": body.name, "grade": body.grade}


@app.get("/students")
def list_students(grade: Optional[int] = None):
    return db.list_students(grade=grade)


@app.get("/students/{student_id}/next")
def next_question(student_id: int):
    student = _require_student(student_id)
    engine, _, _ = _engine_for(student)
    nxt = engine.next_question(student_id)
    if nxt is None:
        return {"done": True, "message": "No questions left to ask for this student."}
    return {"done": False, "question": _question_out(nxt["question"]),
            "concept_id": nxt["concept_id"], "is_review": nxt["is_review"], "reason": nxt["reason"]}


@app.post("/students/{student_id}/attempt")
def submit_attempt(student_id: int, body: AnswerIn):
    student = _require_student(student_id)
    engine, content, _ = _engine_for(student)
    if body.question_id not in content.questions:
        raise HTTPException(404, f"Unknown question_id {body.question_id} for grade {student['grade']}")
    valid_labels = {o["label"] for o in content.question(body.question_id)["options"]}
    if body.option_label not in valid_labels:
        raise HTTPException(400, f"option_label must be one of {sorted(valid_labels)}")
    return engine.submit_answer(student_id, body.question_id, body.option_label,
                                body.is_review, body.time_taken_sec)


@app.get("/students/{student_id}/mastery")
def mastery(student_id: int):
    student = _require_student(student_id)
    _, _, concepts = _engine_for(student)
    m, default_p = db.get_mastery_map(student_id, bkt.DEFAULT_PARAMS.p_init)
    return {cid: {"label": concepts[cid]["label"], "mastery_pct": bkt.to_pct(m.get(cid, default_p))}
            for cid in topo_order(concepts)}


@app.get("/students/{student_id}/report")
def student_report(student_id: int):
    student = _require_student(student_id)
    _, content, concepts = _engine_for(student)
    return report.student_report(student_id, content, concepts)


@app.get("/teacher/dashboard/{grade}")
def dashboard(grade: int):
    if grade not in GRADES:
        raise HTTPException(404, f"grade must be one of {GRADES}")
    return report.teacher_dashboard(CONTENT[grade], GRADE_CONCEPTS[grade], grade)


@app.post("/admin/reset")
def reset():
    """Wipes all students and attempts across every grade. For demo/testing only."""
    db.reset_db()
    return {"status": "reset"}
