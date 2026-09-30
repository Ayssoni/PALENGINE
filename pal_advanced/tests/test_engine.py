"""
Self-tests against the live API (no server process needed - uses FastAPI's TestClient).
Run:  python tests/test_engine.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402
from pal import db  # noqa: E402
from pal.main import app  # noqa: E402

client = TestClient(app)


def correct_label(q):
    # the test client only sees option text, so ask the content module which one is right
    from pal.main import content
    return next(o["label"] for o in content.question(q["question_id"])["options"]
               if content.question(q["question_id"])["correct_option"] == o["label"])


def run_student(name, strategy, max_q=90):
    sid = client.post("/students", json={"name": name}).json()["student_id"]
    log = []
    for i in range(max_q):
        nxt = client.get(f"/students/{sid}/next").json()
        if nxt["done"]:
            break
        q = nxt["question"]
        label = strategy(q)
        ans = client.post(f"/students/{sid}/attempt",
                          json={"question_id": q["question_id"], "option_label": label}).json()
        log.append((nxt["concept_id"], ans["is_correct"], ans["mastery_after_pct"]))
    return sid, log


def test_always_correct_reaches_mastery_and_unlocks_dependents():
    def strat(q):
        return next(o["label"] for o in q["options"]) and correct_label(q)
    sid, log = run_student("Always Correct", strat)
    rep = client.get(f"/students/{sid}/report").json()
    assert rep["accuracy_pct"] > 95, rep["accuracy_pct"]
    # should have mastered multiple concepts including some that require prerequisites
    mastered = {c["concept_id"] for c in rep["concepts"] if c["status"] == "Mastered"}
    assert "part_of_whole" in mastered
    assert "word_problems" in mastered or "dividing" in mastered, mastered  # reached deep into the graph
    print(f"[PASS] always-correct student: {len(log)} answered, {len(mastered)} concepts mastered, "
          f"overall mastery {rep['overall_mastery_pct']}%")


def test_always_wrong_never_advances_past_gate_and_flags_at_risk():
    def strat(q):
        wrongs = [o["label"] for o in q["options"]]
        wrongs.remove(correct_label(q))
        return wrongs[0]
    sid, log = run_student("Always Wrong", strat)
    rep = client.get(f"/students/{sid}/report").json()
    assert rep["accuracy_pct"] < 5, rep["accuracy_pct"]
    concepts_touched = {c for c, _, _ in log}
    # should stay stuck near the start of the graph, never reaching late concepts
    assert "word_problems" not in concepts_touched, "should never reach word problems while always wrong"
    assert len(rep["misconceptions"]) > 0
    dash = client.get("/teacher/dashboard").json()
    flagged = {s["name"] for s in dash["at_risk_students"]}
    assert "Always Wrong" in flagged, flagged
    print(f"[PASS] always-wrong student: stuck after {len(log)} answered on concepts {sorted(concepts_touched)}, "
          f"flagged at-risk: {'Always Wrong' in flagged}")


def test_targeted_misconception_is_detected_and_served():
    rng = random.Random(11)
    # this student consistently believes "larger denominator = larger fraction"
    HABIT = "Believes a larger denominator means a larger fraction"

    def strat(q):
        from pal.main import content
        qd = content.question(q["question_id"])
        habit_opt = next((o for o in qd["options"] if o["mid"] and
                          content.misconceptions[o["mid"]]["description"] == HABIT), None)
        if habit_opt and rng.random() < 0.85:
            return habit_opt["label"]
        return correct_label(q) if rng.random() < 0.6 else rng.choice([o["label"] for o in q["options"]])

    sid, log = run_student("Habit Student", strat, max_q=40)
    rep = client.get(f"/students/{sid}/report").json()
    descs = [m["description"] for m in rep["misconceptions"]]
    assert any(HABIT in d for d in descs), descs
    print(f"[PASS] habit student: detected misconceptions -> {descs[:2]}")


def test_dashboard_aggregates_class():
    dash = client.get("/teacher/dashboard").json()
    assert dash["n_students"] >= 3
    assert dash["n_attempts"] > 50
    assert len(dash["weakest_concepts"]) > 0
    assert len(dash["top_misconceptions"]) > 0
    print(f"[PASS] dashboard: {dash['n_students']} students, {dash['n_attempts']} attempts, "
          f"weakest concept: {dash['weakest_concepts'][0]['label']}")


if __name__ == "__main__":
    db.reset_db()
    test_always_correct_reaches_mastery_and_unlocks_dependents()
    test_always_wrong_never_advances_past_gate_and_flags_at_risk()
    test_targeted_misconception_is_detected_and_served()
    test_dashboard_aggregates_class()
    print("\nAll tests passed.")
