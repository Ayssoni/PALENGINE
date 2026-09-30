"""Loads the fixed content (questions, options, misconceptions) from content_source.db
and attaches each question to a concept_id from config.concepts."""
import sqlite3
from pathlib import Path

from config.concepts import CONCEPTS, LABEL_TO_ID

CONTENT_DB = Path(__file__).resolve().parent.parent / "data" / "content_source.db"


class Content:
    def __init__(self, path=CONTENT_DB):
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row

        self.misconceptions = {r["misconception_id"]: dict(r) for r in con.execute("SELECT * FROM misconceptions")}
        self.guess_ids = {m for m, r in self.misconceptions.items()
                          if r["description"].startswith("Guess or slip")}

        self.questions = {}
        for r in con.execute("SELECT * FROM questions"):
            label = r["subtopic"]
            if label not in LABEL_TO_ID:
                raise ValueError(f"Subtopic '{label}' has no concept mapping in config/concepts.py")
            self.questions[r["question_id"]] = {**dict(r), "concept_id": LABEL_TO_ID[label], "options": []}
        for r in con.execute("SELECT * FROM options ORDER BY question_id, option_label"):
            self.questions[r["question_id"]]["options"].append({
                "label": r["option_label"], "text": r["option_text"],
                "mid": r["misconception_id"], "feedback": r["feedback_text"]})
        con.close()

        # index: concept_id -> [question_id, ...],  and concept_id -> {difficulty -> [question_id,...]}
        self.by_concept = {}
        for qid, q in self.questions.items():
            self.by_concept.setdefault(q["concept_id"], []).append(qid)
        for cid in self.by_concept:
            self.by_concept[cid].sort(key=lambda qid: self.questions[qid]["difficulty"])

        # sanity: every concept in the graph should have at least one question, and vice versa
        missing = [cid for cid in CONCEPTS if cid not in self.by_concept]
        if missing:
            raise ValueError(f"Concepts with no questions: {missing}")

        # misconception_id -> concept_id -> [question_id,...]  (excludes guess/slip tags)
        self.mis_questions = {}
        for qid, q in self.questions.items():
            for o in q["options"]:
                if o["mid"] and o["mid"] not in self.guess_ids:
                    self.mis_questions.setdefault(o["mid"], {}).setdefault(q["concept_id"], []).append(qid)

    def question(self, qid):
        return self.questions[qid]

    def questions_for_concept(self, cid, exclude=()):
        return [q for q in self.by_concept.get(cid, []) if q not in exclude]

    def pick_by_mastery(self, candidates, p_mastery):
        """Order candidates by difficulty and pick one near the student's current mastery level."""
        cand = sorted(candidates, key=lambda qid: self.questions[qid]["difficulty"])
        idx = min(len(cand) - 1, max(0, int(round(p_mastery * (len(cand) - 1)))))
        return cand[idx]
