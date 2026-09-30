# PAL Fractions - Advanced Prototype (BKT, multi-student, FastAPI)

An adaptive-learning prototype for the fractions chapter, built on Bayesian Knowledge Tracing
(BKT), a 24-concept prerequisite graph, misconception detection, spaced review, and a
FastAPI backend that supports many students, with a teacher dashboard.

## What's new versus the single-user Streamlit prototype
| | Single-user prototype | This version |
|---|---|---|
| Mastery model | Elo-style rating | **Bayesian Knowledge Tracing** (P(L), P(T), P(G), P(S) per concept) |
| Structure | One difficulty ladder | **24-concept prerequisite graph** (`config/concepts.py`) |
| Users | One (you) | **Many students**, own progress each |
| Backend | None (Streamlit called the engine directly) | **FastAPI** service, callable from any client |
| Views | One quiz screen | **Student app + teacher dashboard**, both talk to the API |
| Progression | Score-based staircase | **Gated by real BKT mastery** - a student who keeps a concept wrong is never pushed past it, even if that concept's question bank runs out (it recycles questions rather than pretending the gate is satisfied) |
| Review | None | **Spaced review**: once concepts are mastered, the least-recently-practiced one resurfaces every 5 questions |

## Run it

**1. Start the API** (from `pal_advanced/`):
```
pip install -r requirements.txt
uvicorn pal.main:app --reload --port 8000
```
Check it's up: http://127.0.0.1:8000/health   (interactive docs at `/docs`)

**2. Start the student app** (new terminal):
```
streamlit run ui/student_app.py --server.port 8501
```

**3. Start the teacher dashboard** (another terminal):
```
streamlit run ui/teacher_app.py --server.port 8502
```

All three must run at the same time; the two Streamlit apps are just clients of the API.

## How the engine decides what to ask (`pal/selection.py`)

1. **Confirmed misconception** (same wrong-option tag twice since the last correct answer on
   that concept) → a question on the same concept that targets it.
2. **Frontier concept**: walk the prerequisite graph in order; the first concept whose real BKT
   mastery is below 80% but whose prerequisites are ALL at or above 80% is the focus. A question
   near the student's current mastery of it is chosen.
   - If that concept's question bank is used up before mastery is reached, the engine **repeats**
     one of its questions rather than moving on - the prerequisite gate is never bypassed just
     because a small content bank ran out. (This is the main gap for a real deployment: a full
     content bank needs enough questions per concept that this rarely triggers.)
3. **Spaced review**: once every concept is mastered, the engine resurfaces the mastered concept
   that's gone longest without practice, every 5 questions.

## BKT parameters (`pal/bkt.py`)
```
p_init    = 0.30   prior probability of mastery before any evidence
p_transit = 0.15   probability of learning the skill after one question
p_guess   = 0.22   probability of a correct answer without having mastered it (4-option MCQ)
p_slip    = 0.10   probability of a wrong answer despite having mastered it
```
These are reasonable defaults, not calibrated on real students. `MASTERY_THRESHOLD = 0.80` is
the standard BKT cutoff for "mastered." Tune both once you have real attempt data.

## API summary
| Endpoint | Purpose |
|---|---|
| `POST /students` | Create a student |
| `GET /students/{id}/next` | Get the next question (the decision tree above) |
| `POST /students/{id}/attempt` | Submit an answer, get feedback + updated mastery |
| `GET /students/{id}/mastery` | Per-concept mastery (%) |
| `GET /students/{id}/report` | Full student report: mastery, misconceptions, recommendations |
| `GET /teacher/dashboard` | Class-wide: weakest concepts, top misconceptions, at-risk students |
| `POST /admin/reset` | Wipes all students/attempts (demo only) |

## Tested behaviour (`tests/test_engine.py`)
Run with `python tests/test_engine.py` (starts the API in-process, no server needed):
- An **always-correct** simulated student reaches mastery on all 24 concepts.
- An **always-wrong** simulated student gets stuck honestly on the very first concept for 90
  attempts straight, and is flagged **at-risk** on the teacher dashboard - it never gets pushed
  into later concepts it hasn't shown mastery of.
- A student with one **consistent habit** ("larger denominator = larger fraction") has that
  misconception detected and named in their report.
- The **teacher dashboard** correctly aggregates multiple students.

This test suite is what caught two real bugs during development: a gating bug that let an
always-wrong student reach advanced concepts once a small question bank ran dry, and a mismatch
between the student report's overall mastery figure and the sidebar/dashboard figure. Both are
fixed; re-run the tests after any change to `pal/selection.py` or `pal/report.py`.

## Known limitations (be upfront about these)
- **Question bank is small per concept** (about 4 on average). Real deployment needs more
  questions per concept so the "repeat" fallback in the frontier logic rarely triggers.
- **BKT parameters are defaults, not fitted.** Calibrate `p_guess`/`p_slip`/`p_transit` per
  concept once real student data exists (standard tools: `pyBKT`, EM fitting).
- **The concept graph is a teacher judgement call**, not derived from data. Review it in
  `config/concepts.py` and adjust prerequisites to match how your curriculum actually sequences
  fractions.
- **Single subject, single chapter.** Multi-subject support means giving each subject its own
  concept graph and content bank, sharing the same engine and database schema.
- **No auth.** Anyone who can reach the API can act as any student ID. Fine for a prototype;
  add login before any real classroom use.

## Files
```
pal_advanced/
├── config/concepts.py     concept graph (24 concepts, prerequisites)
├── pal/
│   ├── bkt.py              Bayesian Knowledge Tracing update rule
│   ├── content.py          loads questions/options/misconceptions, maps to concepts
│   ├── db.py               SQLite: students, per-concept mastery, attempt log
│   ├── selection.py        the decision tree (frontier + misconception + review)
│   ├── report.py           student report + teacher dashboard aggregation
│   └── main.py             FastAPI app
├── ui/
│   ├── student_app.py      Streamlit: practice + personal report
│   └── teacher_app.py      Streamlit: class dashboard
├── tests/test_engine.py    simulated-student tests (run without a server)
└── data/content_source.db  the 100-question fractions content (read-only source)
```

## Reset everything
```
rm data/pal_advanced.db      # wipes all students and attempts; recreated on next API start
```
