"""
PAL backend API (BKT-driven prototype, multi-student).

Run:  uvicorn pal.main:app --reload --port 8000
Docs: http://127.0.0.1:8000/docs
"""
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config.concepts import CONCEPTS, topo_order
from pal import bkt, db, report
from pal.content import Content
from pal.selection import SelectionEngine

app = FastAPI(title="PAL Fractions API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db.init_db()
content = Content()
engine = SelectionEngine(content)


class NewStudent(BaseModel):
    name: str
    school: Optional[str] = None
    grade: Optional[str] = None


class AnswerIn(BaseModel):
    question_id: str
    option_label: str
    is_review: bool = False
    time_taken_sec: Optional[float] = None


def _question_out(q):
    return {"question_id": q["question_id"], "subtopic": q["subtopic"], "concept_id": q["concept_id"],
            "difficulty": q["difficulty"], "question_text": q["question_text"],
            "options": [{"label": o["label"], "text": o["text"]} for o in q["options"]]}


@app.get("/health")
def health():
    return {"status": "ok", "concepts": len(CONCEPTS), "questions": len(content.questions)}


@app.get("/concepts")
def list_concepts():
    return {"order": topo_order(), "concepts": CONCEPTS}


@app.post("/students")
def create_student(body: NewStudent):
    sid = db.create_student(body.name, body.school, body.grade)
    return {"student_id": sid, "name": body.name}


@app.get("/students")
def list_students():
    return db.list_students()


def _require_student(student_id: int):
    s = db.get_student(student_id)
    if not s:
        raise HTTPException(404, f"No student with id {student_id}")
    return s


@app.get("/students/{student_id}/next")
def next_question(student_id: int):
    _require_student(student_id)
    nxt = engine.next_question(student_id)
    if nxt is None:
        return {"done": True, "message": "No questions left to ask for this student."}
    return {"done": False, "question": _question_out(nxt["question"]),
            "concept_id": nxt["concept_id"], "is_review": nxt["is_review"], "reason": nxt["reason"]}


@app.post("/students/{student_id}/attempt")
def submit_attempt(student_id: int, body: AnswerIn):
    _require_student(student_id)
    if body.question_id not in content.questions:
        raise HTTPException(404, f"Unknown question_id {body.question_id}")
    valid_labels = {o["label"] for o in content.question(body.question_id)["options"]}
    if body.option_label not in valid_labels:
        raise HTTPException(400, f"option_label must be one of {sorted(valid_labels)}")
    return engine.submit_answer(student_id, body.question_id, body.option_label,
                                body.is_review, body.time_taken_sec)


@app.get("/students/{student_id}/mastery")
def mastery(student_id: int):
    _require_student(student_id)
    m, default_p = db.get_mastery_map(student_id, bkt.DEFAULT_PARAMS.p_init)
    return {cid: {"label": CONCEPTS[cid]["label"], "mastery_pct": bkt.to_pct(m.get(cid, default_p))}
            for cid in topo_order()}


@app.get("/students/{student_id}/report")
def student_report(student_id: int):
    _require_student(student_id)
    return report.student_report(student_id, content)


@app.get("/teacher/dashboard")
def dashboard():
    return report.teacher_dashboard(content)


@app.post("/admin/reset")
def reset():
    """Wipes all students and attempts. For demo/testing only."""
    db.reset_db()
    return {"status": "reset"}
