"""
The decision tree, now driven by BKT mastery and a prerequisite graph, plus spaced review.

next_question(student_id) picks, in order:
    1. A confirmed misconception (>=2 hits in the recent run on that concept) -> targeted question
       on the SAME concept (fixing understanding before moving on).
    2. The frontier concept: the earliest concept (in prerequisite order) whose prerequisites are
       all mastered (p >= MASTERY_THRESHOLD) but which is not itself mastered yet -> a question at
       a difficulty matched to the student's current mastery of it.
    3. If every concept is mastered, spaced review: revisit whichever mastered concept has gone
       longest without practice (weakest recent evidence), every REVIEW_EVERY questions.
    4. If nothing is left to ask, None (chapter complete).

submit_answer(...) runs the BKT update, logs the attempt, and returns feedback content plus
whether a misconception was just confirmed.
"""
import random

from config.concepts import CONCEPTS, topo_order
from pal import bkt, db

REVIEW_EVERY = 5           # inject one review question every N answered, once the frontier is clear
CONFIRM_AT = 2              # same misconception this many times (since the last correct) -> confirmed


class SelectionEngine:
    def __init__(self, content):
        self.content = content
        self.order = topo_order()

    # -------------------------------------------------------------- read state
    def mastery_map(self, student_id):
        stored, default_p = db.get_mastery_map(student_id, bkt.DEFAULT_PARAMS.p_init)
        return {cid: stored.get(cid, default_p) for cid in CONCEPTS}

    def frontier_concept(self, mastery):
        for cid in self.order:
            if mastery[cid] < bkt.MASTERY_THRESHOLD:
                prereqs = CONCEPTS[cid]["prereqs"]
                if all(mastery[p] >= bkt.MASTERY_THRESHOLD for p in prereqs):
                    return cid
        return None   # everything mastered

    # -------------------------------------------------------------- pick next question
    def next_question(self, student_id):
        """
        IMPORTANT gating rule: a concept only counts as a satisfied prerequisite when its REAL
        BKT mastery crosses the threshold. Running out of unused questions for a concept never
        substitutes for mastery - it only changes what we serve right now (a repeat, for honest
        remedial practice), never what gets unlocked next. This is what stops a student who keeps
        getting a concept wrong from ever being pushed into questions that assume they've learned it.
        """
        mastery = self.mastery_map(student_id)
        asked = db.asked_questions(student_id)
        attempts = db.student_attempts(student_id)
        attempts_so_far = len(attempts)
        last_qid = attempts[-1]["question_id"] if attempts else None

        def serve_from(cid, pool_all, reason_new, reason_repeat):
            cand = [q for q in pool_all if q not in asked]
            if cand:
                return self._pack(self.content.pick_by_mastery(cand, mastery[cid]), cid, False, reason_new)
            recycle = [q for q in pool_all if q != last_qid] or pool_all
            if recycle:
                return self._pack(self.content.pick_by_mastery(recycle, mastery[cid]), cid, False, reason_repeat)
            return None

        # 1. confirmed misconception -> targeted question on the same concept (repeats allowed:
        #    fixing the misunderstanding matters more than novelty here)
        for a in reversed(attempts):
            if a["is_correct"] or not a["misconception_id"]:
                break
            cid, mid = a["concept_id"], a["misconception_id"]
            if db.recent_misconception_run(student_id, cid, mid) >= CONFIRM_AT:
                pool = self.content.mis_questions.get(mid, {}).get(cid, [])
                if pool:
                    desc = self.content.misconceptions[mid]["description"]
                    r = serve_from(cid, pool,
                        f"Targeted practice: you repeated this mistake - \"{desc}\". This checks whether it's fixed.",
                        f"Targeted practice (repeat question): still checking on \"{desc}\".")
                    if r:
                        return r
            break  # only look at the most recent wrong streak

        # 2. frontier concept - the earliest concept (by real mastery) whose prerequisites are met
        frontier = self.frontier_concept(mastery)
        if frontier is not None:
            label = CONCEPTS[frontier]["label"]
            pct = bkt.to_pct(mastery[frontier])
            new_reason = (f"Starting concept: '{label}'." if attempts_so_far else
                         f"Focus concept: '{label}' (mastery {pct}%, prerequisites met).")
            repeat_reason = (f"Repeat practice on '{label}' (mastery {pct}%): no new questions left for it yet, "
                            f"and it isn't confirmed as mastered, so we keep practising it rather than move on.")
            r = serve_from(frontier, self.content.questions_for_concept(frontier), new_reason, repeat_reason)
            if r:
                return r
            return None  # frontier concept truly has zero questions at all (content gap)

        # 3. every concept's real mastery is at/above threshold -> spaced review
        mastered = list(CONCEPTS)
        if attempts_so_far and attempts_so_far % REVIEW_EVERY == 0:
            due = self._least_recent(student_id, mastered)
            r = serve_from(due, self.content.questions_for_concept(due),
                           f"Spaced review: revisiting '{CONCEPTS[due]['label']}' to check it has stuck.",
                           f"Spaced review (repeat): revisiting '{CONCEPTS[due]['label']}' again.")
            if r:
                return r

        # 4. fully mastered and not due for review this turn - still give something rather than stop
        due = self._least_recent(student_id, mastered)
        return serve_from(due, self.content.questions_for_concept(due),
                          f"Extra practice: '{CONCEPTS[due]['label']}'.",
                          f"Extra practice (repeat): '{CONCEPTS[due]['label']}'.")

    def _least_recent(self, student_id, concept_ids):
        attempts = db.student_attempts(student_id)
        last_index = {cid: -1 for cid in concept_ids}
        for i, a in enumerate(attempts):
            if a["concept_id"] in last_index:
                last_index[a["concept_id"]] = i
        return min(concept_ids, key=lambda c: last_index[c])

    def _pack(self, qid, concept_id, is_review, reason):
        return {"question": self.content.question(qid), "concept_id": concept_id,
                "is_review": is_review, "reason": reason}

    # -------------------------------------------------------------- process an answer
    def submit_answer(self, student_id, question_id, chosen_label, is_review=False, time_taken=None):
        q = self.content.question(question_id)
        concept_id = q["concept_id"]
        opt = next(o for o in q["options"] if o["label"] == chosen_label)
        correct_opt = next(o for o in q["options"] if o["mid"] is None)
        is_correct = opt["mid"] is None
        mid = opt["mid"] if not is_correct and opt["mid"] not in self.content.guess_ids else \
              (opt["mid"] if not is_correct else None)

        p_before = db.get_concept_mastery(student_id, concept_id, bkt.DEFAULT_PARAMS.p_init)
        p_after = bkt.update(p_before, is_correct)
        db.set_concept_mastery(student_id, concept_id, p_after)
        db.log_attempt(student_id, question_id, concept_id, chosen_label, is_correct,
                       opt["mid"], is_review, time_taken, p_before, p_after)

        confirmed = False
        if not is_correct and opt["mid"] and opt["mid"] not in self.content.guess_ids:
            confirmed = db.recent_misconception_run(student_id, concept_id, opt["mid"]) >= CONFIRM_AT

        crossed_mastery = p_before < bkt.MASTERY_THRESHOLD <= p_after
        m = self.content.misconceptions.get(opt["mid"]) if opt["mid"] else None
        return {
            "is_correct": is_correct, "concept_id": concept_id, "concept_label": CONCEPTS[concept_id]["label"],
            "chosen_label": chosen_label, "chosen_text": opt["text"],
            "correct_label": correct_opt["label"], "correct_text": correct_opt["text"],
            "explanation": q["explanation"], "feedback": opt["feedback"],
            "misconception": m["description"] if m else None,
            "remedy": m["remedy_text"] if m else None,
            "is_guess_tag": bool(opt["mid"] and opt["mid"] in self.content.guess_ids),
            "confirmed": confirmed,
            "p_mastery_before": round(p_before, 3), "p_mastery_after": round(p_after, 3),
            "mastery_before_pct": bkt.to_pct(p_before), "mastery_after_pct": bkt.to_pct(p_after),
            "concept_mastered_now": crossed_mastery,
        }
