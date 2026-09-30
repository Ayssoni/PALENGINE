# PAL Fractions - Grade-Aware Prototype (BKT, multi-student, FastAPI)

An adaptive-learning prototype covering Class 6, 7 and 8 fractions content, built on Bayesian
Knowledge Tracing (BKT), a per-grade prerequisite graph, misconception detection, spaced review,
and a FastAPI backend supporting many students with a teacher dashboard.

## What's new versus the single-grade version
| | Before | Now |
|---|---|---|
| Content | One database, all 100 questions mixed together | **Three databases** (`data/grade6.db`, `grade7.db`, `grade8.db`), 56 / 34 / 10 questions |
| Concept graph | One 24-concept graph | **Three subgraphs** - each grade only gates on its OWN concepts. A grade-7 concept that depends on a grade-6 skill (e.g. "adding unlike fractions" needs "equivalent fractions") drops that prerequisite for the grade-7 engine - a 7th grader is assumed to already have it, having passed grade 6 |
| Students | Ungraded | Every student has a **grade** (6, 7 or 8), fixed at creation, which decides everything they see |
| Mastery/attempts | Shared pool | **Fully isolated per grade** - a grade-6 student's attempts never appear in a grade-7 dashboard, and vice versa |
| Dashboard | One combined view | `GET /teacher/dashboard/{grade}` - a separate dashboard per grade |

## Run it
```
pip install -r requirements.txt
uvicorn pal.main:app --reload --port 8000            # terminal 1
streamlit run ui/student_app.py --server.port 8501   # terminal 2 (now asks for a grade first)
streamlit run ui/teacher_app.py --server.port 8502    # terminal 3 (now has a grade selector)
```

## How grades work under the hood

**`config/concepts.py`** tags every concept with a grade and keeps prerequisites pointing only
at concepts of the same or an earlier grade (this is checked by an assertion at import time).
`get_grade_concepts(grade)` returns a self-contained subgraph: only that grade's concepts, with
any earlier-grade prerequisite silently dropped (since it's assumed already known).

**`pal/main.py`** builds three independent `Content` + `SelectionEngine` pairs at startup, one
per grade, from `GRADE_CONCEPTS = {6: ..., 7: ..., 8: ...}`. Every endpoint looks up the
student's stored `grade` and routes to that grade's engine - a student can never be served a
question or accumulate mastery outside their own grade's graph.

**`pal/db.py`** stores `grade` on the `students` table. `concept_mastery` and `attempts` don't
need a grade column themselves - concept ids are already grade-specific (e.g. `add_unlike` only
exists in grade 7), so there's no way for a grade-6 student's row to collide with a grade-7
concept.

## Decision tree (same logic as before, now scoped per grade)
1. **Confirmed misconception** (same wrong-option tag twice since the last correct answer on
   that concept) → a question on the same concept, from that grade's bank.
2. **Frontier concept**: the first concept (within THIS grade's graph) whose mastery is below
   80% but whose prerequisites (also within this grade) are all met.
   - If that concept's small question bank runs dry before mastery is reached, the engine
     repeats one of its questions rather than moving on - the gate is never bypassed.
3. **Spaced review**: once every concept in the grade is mastered, the longest-unpracticed one
   resurfaces every 5 questions.

## Tested behaviour (`tests/test_engine.py`)
Run with `python tests/test_engine.py` (starts the API in-process). 11 checks, including:
- **Grade isolation**: grade 6 and grade 8 concept id sets are disjoint; a grade-6 student is
  only ever served grade-6 concepts.
- Grade 9 (unsupported) is rejected with a 422.
- For **each of the three grades**: an always-correct student masters every concept in that
  grade's graph, and an always-wrong student gets stuck honestly on that grade's very first
  concept for all 90 attempts, flagged at-risk.
- **No cross-grade leakage**: a grade-6 dashboard and a grade-7 dashboard never show each
  other's students.
- A realistic ~70%-correct grade-7 student progresses sensibly through the graph.

This suite caught a real bug during this round of changes: the `/grades` endpoint returns a
JSON object, and JSON object keys are always strings - so `{6: ...}` comes back as `{"6": ...}`.
The Streamlit student app compared that string grade against the database's integer grade and
silently found no students. Both UI files now cast the keys back to `int` right after fetching.
Re-run the tests after any change to `pal/selection.py`, `pal/report.py`, or the two UI files.

## Known limitations
- **Grade 8 has only 10 questions across 2 subtopics** (see `pal_grades/README.md` for why -
  it's word problems repurposed as a placeholder, not a real Grade 8 chapter).
- **The grade-to-subtopic mapping is a curriculum judgement call**, not derived from data -
  see `GRADE_OF_SUBTOPIC` in the original `split_by_grade.py` (in `pal_grades/`) for the mapping
  that produced `data/grade{6,7,8}.db`.
- **BKT parameters are sensible defaults, not calibrated** on real students yet.
- **No authentication**, and no enforcement that a student can't claim a different grade than
  they're actually in. Fine for a prototype, not for real classroom use.
- **A student's grade is fixed at creation.** Promoting a student from grade 6 to grade 7
  (end of year) isn't implemented - it would mean copying their id to a new grade with a fresh
  mastery map, since the concept graphs don't overlap.

## Files
```
pal_advanced/
├── config/concepts.py     concept graph for all 3 grades + get_grade_concepts()
├── pal/
│   ├── bkt.py              Bayesian Knowledge Tracing update rule
│   ├── content.py          loads one grade's DB, validated against that grade's concepts
│   ├── db.py               SQLite: students (with grade), per-concept mastery, attempt log
│   ├── selection.py        the decision tree, scoped to one grade's concept set
│   ├── report.py           student report + per-grade teacher dashboard
│   └── main.py             FastAPI app - builds one engine per grade at startup
├── ui/
│   ├── student_app.py      Streamlit: grade picker, practice, personal report
│   └── teacher_app.py      Streamlit: grade selector, class dashboard
├── tests/test_engine.py    grade-isolation + simulated-student tests
└── data/
    ├── grade6.db            56 questions, 14 concepts
    ├── grade7.db            34 questions, 8 concepts
    └── grade8.db            10 questions, 2 concepts
```

## Reset everything
```
rm data/pal_advanced.db      # wipes all students and attempts, every grade; recreated on next API start
```
