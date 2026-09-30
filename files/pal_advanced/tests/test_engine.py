"""
Self-tests against the live API (uses FastAPI's TestClient, no server process needed).
Run:  python tests/test_engine.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402
from pal import db  # noqa: E402
from pal.main import app, CONTENT  # noqa: E402

client = TestClient(app)


def correct_label(qid, grade):
    content = CONTENT[grade]
    q = content.question(qid)
    return q["correct_option"]


def run_student(name, grade, strategy, max_q=90):
    sid = client.post("/students", json={"name": name, "grade": grade}).json()["student_id"]
    log = []
    for i in range(max_q):
        nxt = client.get(f"/students/{sid}/next").json()
        if nxt["done"]:
            break
        q = nxt["question"]
        label = strategy(q, grade)
        ans = client.post(f"/students/{sid}/attempt",
                          json={"question_id": q["question_id"], "option_label": label}).json()
        log.append((nxt["concept_id"], ans["is_correct"], ans["mastery_after_pct"]))
    return sid, log


def test_grade_isolation():
    """A grade-6 student and a grade-8 student never see each other's concepts or questions."""
    r6 = client.get("/grades/6/concepts").json()
    r8 = client.get("/grades/8/concepts").json()
    assert set(r6["concepts"]) & set(r8["concepts"]) == set(), "grade 6 and grade 8 concept ids overlap"
    sid6 = client.post("/students", json={"name": "Grade6 Kid", "grade": 6}).json()["student_id"]
    nxt = client.get(f"/students/{sid6}/next").json()
    assert nxt["question"]["concept_id"] in r6["concepts"], "grade-6 student served a non-grade-6 concept"
    print("[PASS] grade isolation: grade 6 and grade 8 concept sets are disjoint, "
          f"grade-6 student served concept '{nxt['concept_id']}' from grade 6's own set")


def test_invalid_grade_rejected():
    r = client.post("/students", json={"name": "Bad Grade", "grade": 9})
    assert r.status_code == 422, r.status_code
    print("[PASS] grade 9 (unsupported) rejected with", r.status_code)


def test_always_correct_masters_all_concepts_within_grade(grade):
    def strat(q, g):
        return correct_label(q["question_id"], g)
    sid, log = run_student(f"Always Correct G{grade}", grade, strat)
    rep = client.get(f"/students/{sid}/report").json()
    assert rep["grade"] == grade
    assert rep["accuracy_pct"] > 95, rep["accuracy_pct"]
    mastered = {c["concept_id"] for c in rep["concepts"] if c["status"] == "Mastered"}
    assert len(mastered) == rep["concepts_total"], (len(mastered), rep["concepts_total"])
    print(f"[PASS] grade {grade} always-correct: {len(log)} answered, "
          f"{len(mastered)}/{rep['concepts_total']} concepts mastered")


def test_always_wrong_stuck_at_first_concept(grade):
    def strat(q, g):
        content = CONTENT[g]
        corr = content.question(q["question_id"])["correct_option"]
        wrongs = [o["label"] for o in q["options"] if o["label"] != corr]
        return wrongs[0]
    sid, log = run_student(f"Always Wrong G{grade}", grade, strat)
    rep = client.get(f"/students/{sid}/report").json()
    assert rep["accuracy_pct"] < 5, rep["accuracy_pct"]
    concepts_touched = {c for c, _, _ in log}
    order = client.get(f"/grades/{grade}/concepts").json()["order"]
    first_concept = order[0]
    assert concepts_touched == {first_concept}, (
        f"grade {grade}: expected student to stay stuck on '{first_concept}', touched {concepts_touched}")
    dash = client.get(f"/teacher/dashboard/{grade}").json()
    flagged = {s["name"] for s in dash["at_risk_students"]}
    assert f"Always Wrong G{grade}" in flagged
    print(f"[PASS] grade {grade} always-wrong: stuck on '{first_concept}' for all {len(log)} attempts, flagged at-risk")


def test_cross_grade_no_leakage():
    """Attempts and mastery for a grade-6 student must not appear in a grade-7 dashboard."""
    dash6 = client.get("/teacher/dashboard/6").json()
    dash7 = client.get("/teacher/dashboard/7").json()
    names6 = {s["name"] for s in dash6["students"]}
    names7 = {s["name"] for s in dash7["students"]}
    assert not any("G6" in n for n in names7), f"grade-6 students leaked into grade-7 dashboard: {names7}"
    assert not any("G7" in n for n in names6), f"grade-7 students leaked into grade-6 dashboard: {names6}"
    print(f"[PASS] no cross-grade leakage: grade 6 dashboard has {len(names6)} students, "
          f"grade 7 dashboard has {len(names7)} students, no overlap by construction")


def test_realistic_mixed_student(grade=7):
    rng = random.Random(42)

    def strat(q, g):
        corr = correct_label(q["question_id"], g)
        if rng.random() < 0.7:
            return corr
        return rng.choice([o["label"] for o in q["options"] if o["label"] != corr])

    sid, log = run_student("Realistic G7", grade, strat, max_q=50)
    rep = client.get(f"/students/{sid}/report").json()
    assert 0 < rep["accuracy_pct"] < 100
    print(f"[PASS] grade {grade} realistic (~70% correct): accuracy {rep['accuracy_pct']}%, "
          f"overall mastery {rep['overall_mastery_pct']}%, "
          f"{rep['concepts_mastered']}/{rep['concepts_total']} mastered")


if __name__ == "__main__":
    db.reset_db()
    test_grade_isolation()
    test_invalid_grade_rejected()
    for g in (6, 7, 8):
        test_always_correct_masters_all_concepts_within_grade(g)
        test_always_wrong_stuck_at_first_concept(g)
    test_cross_grade_no_leakage()
    test_realistic_mixed_student(7)
    print("\nAll tests passed.")
