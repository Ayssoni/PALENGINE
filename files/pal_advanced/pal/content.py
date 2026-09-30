"""Loads the fixed content (questions, options, misconceptions) from a content DB
and attaches each question to a concept_id, validated against a given concept set
(pass a grade-scoped subset from config.concepts.get_grade_concepts for a single-grade DB)."""
import sqlite3
from pathlib import Path

from config.concepts import CONCEPTS as _ALL_CONCEPTS
from config.concepts import LABEL_TO_ID

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Content:
    def __init__(self, path, concepts=None):
        """`concepts` is the concept dict this content is expected to cover (e.g. a single
        grade's subgraph). Defaults to the full CONCEPTS set for backward compatibility."""
        self.concepts = concepts if concepts is not None else _ALL_CONCEPTS
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
            cid = LABEL_TO_ID[label]
            if cid not in self.concepts:
                raise ValueError(f"Subtopic '{label}' (concept '{cid}') is not in the expected concept set "
                                 f"for this content DB ({path}). Wrong grade's database loaded?")
            self.questions[r["question_id"]] = {**dict(r), "concept_id": cid, "options": []}
        for r in con.execute("SELECT * FROM options ORDER BY question_id, option_label"):
            self.questions[r["question_id"]]["options"].append({
                "label": r["option_label"], "text": r["option_text"],
                "mid": r["misconception_id"], "feedback": r["feedback_text"]})
        con.close()

        # index: concept_id -> [question_id, ...]
        self.by_concept = {}
        for qid, q in self.questions.items():
            self.by_concept.setdefault(q["concept_id"], []).append(qid)
        for cid in self.by_concept:
            self.by_concept[cid].sort(key=lambda qid: self.questions[qid]["difficulty"])

        # sanity: every concept expected for this content should have at least one question
        missing = [cid for cid in self.concepts if cid not in self.by_concept]
        if missing:
            raise ValueError(f"Concepts with no questions in {path}: {missing}")

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
