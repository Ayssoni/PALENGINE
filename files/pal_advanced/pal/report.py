"""Reports: one student's progress, and the teacher's grade-wise class dashboard.
Both take `concepts` explicitly (a grade's subgraph) so a grade-8 dashboard never averages
in grade-6 concepts, and vice versa."""
from collections import Counter, defaultdict

from config.concepts import topo_order
from pal import bkt, db


def student_report(student_id, content, concepts):
    student = db.get_student(student_id)
    attempts = db.student_attempts(student_id)
    mastery, default_p = db.get_mastery_map(student_id, bkt.DEFAULT_PARAMS.p_init)

    concepts_out = []
    for cid in topo_order(concepts):
        p = mastery.get(cid, default_p)
        c_attempts = [a for a in attempts if a["concept_id"] == cid]
        status = "Not started" if not c_attempts else (
            "Mastered" if p >= bkt.MASTERY_THRESHOLD else "In progress")
        concepts_out.append({
            "concept_id": cid, "label": concepts[cid]["label"],
            "mastery_pct": bkt.to_pct(p), "status": status,
            "attempts": len(c_attempts),
            "accuracy_pct": round(100 * sum(a["is_correct"] for a in c_attempts) / len(c_attempts), 1) if c_attempts else None,
        })

    n = len(attempts)
    correct = sum(a["is_correct"] for a in attempts)
    # average across every concept in THIS GRADE's graph (untouched concepts count at their
    # BKT prior, not zero and not excluded) - must match the /mastery endpoint and the dashboard
    overall_mastery = round(sum(c["mastery_pct"] for c in concepts_out) / len(concepts_out), 1)

    wrong = [a for a in attempts if not a["is_correct"] and a["misconception_id"]]
    real_wrong = [a for a in wrong if a["misconception_id"] not in content.guess_ids]
    mis_counter = Counter(a["misconception_id"] for a in real_wrong)
    misconceptions = [{"misconception_id": mid, "description": content.misconceptions[mid]["description"],
                       "remedy": content.misconceptions[mid]["remedy_text"], "times": n_}
                      for mid, n_ in mis_counter.most_common()]

    recs = []
    for m in misconceptions:
        if m["times"] >= 2:
            recs.append(f"Repeated mistake ({m['times']}x): {m['description']}. Fix: {m['remedy']}")
    weak = [c for c in concepts_out if c["accuracy_pct"] is not None and c["accuracy_pct"] < 50 and c["attempts"] >= 2]
    for c in weak:
        recs.append(f"Revise '{c['label']}': {c['accuracy_pct']}% correct so far.")
    mastered_concepts = [c for c in concepts_out if c["status"] == "Mastered"]
    if not recs and mastered_concepts:
        recs.append("No repeated mistakes found. Keep going with the next concept.")
    if not recs:
        recs.append("Not enough attempts yet for a recommendation.")

    return {
        "student": student, "grade": student["grade"], "n_attempts": n,
        "accuracy_pct": round(100 * correct / n, 1) if n else 0.0,
        "overall_mastery_pct": overall_mastery,
        "concepts_mastered": len(mastered_concepts), "concepts_total": len(concepts),
        "concepts": concepts_out, "misconceptions": misconceptions, "recommendations": recs,
        "timeline": [{"n": i + 1, "concept": a["concept_id"], "mastery_pct": bkt.to_pct(a["p_mastery_after"])}
                    for i, a in enumerate(attempts)],
    }


def teacher_dashboard(content, concepts, grade):
    """Aggregates only students in this grade, using this grade's concept set - a student in
    grade 6 never pulls down (or props up) a grade 8 average, since they're different graphs
    with different mastery entirely."""
    students = db.list_students(grade=grade)
    all_a = db.all_attempts(grade=grade)

    per_student = []
    concept_sums = defaultdict(lambda: [0.0, 0])
    mis_counter_class = Counter()

    for s in students:
        sid = s["student_id"]
        mastery, default_p = db.get_mastery_map(sid, bkt.DEFAULT_PARAMS.p_init)
        s_attempts = [a for a in all_a if a["student_id"] == sid]
        overall = round(sum(bkt.to_pct(mastery.get(c, default_p)) for c in concepts) / len(concepts), 1)
        acc = round(100 * sum(a["is_correct"] for a in s_attempts) / len(s_attempts), 1) if s_attempts else None
        per_student.append({"student_id": sid, "name": s["name"], "attempts": len(s_attempts),
                            "accuracy_pct": acc, "overall_mastery_pct": overall,
                            "at_risk": bool(s_attempts) and (overall < 40 or (acc is not None and acc < 40))})
        for cid in concepts:
            if any(a["concept_id"] == cid for a in s_attempts):
                concept_sums[cid][0] += bkt.to_pct(mastery.get(cid, default_p))
                concept_sums[cid][1] += 1

    for a in all_a:
        if not a["is_correct"] and a["misconception_id"] and a["misconception_id"] not in content.guess_ids:
            mis_counter_class[a["misconception_id"]] += 1

    concept_avgs = []
    for cid in topo_order(concepts):
        s_sum, n_ = concept_sums[cid]
        if n_:
            concept_avgs.append({"concept_id": cid, "label": concepts[cid]["label"],
                                 "class_avg_mastery_pct": round(s_sum / n_, 1), "students_attempted": n_})
    weakest_concepts = sorted(concept_avgs, key=lambda c: c["class_avg_mastery_pct"])[:5]

    top_misconceptions = [{"misconception_id": mid, "description": content.misconceptions[mid]["description"],
                           "remedy": content.misconceptions[mid]["remedy_text"], "times": n_}
                          for mid, n_ in mis_counter_class.most_common(8)]

    return {
        "grade": grade, "n_students": len(students), "n_attempts": len(all_a),
        "students": sorted(per_student, key=lambda s: s["overall_mastery_pct"]),
        "at_risk_students": [s for s in per_student if s["at_risk"]],
        "concept_averages": concept_avgs, "weakest_concepts": weakest_concepts,
        "top_misconceptions": top_misconceptions,
    }
