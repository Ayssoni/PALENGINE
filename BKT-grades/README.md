# Fractions dataset, split by grade (6, 7, 8)

Built from the existing 100-question fractions bank, split by subtopic into three grades
following the usual NCERT-style progression. Same question format as before: one row per
option, each wrong option tagged with a misconception and feedback text.

## Grade split (curriculum judgement call - adjust to your actual syllabus)

| Grade | Focus | Questions | Subtopics |
|---|---|---|---|
| **6** | What a fraction is, equivalence, simplifying, comparing, like-fraction add/sub, fraction of a quantity | 56 | 14 |
| **7** | Full arithmetic: unlike-fraction add/sub, mixed numbers, multiplying, dividing | 34 | 8 |
| **8** | Applying fractions in multi-step word problems | 10 | 2 |

The mapping is in `split_by_grade.py` as `GRADE_OF_SUBTOPIC` - a plain dictionary, so you can
move any subtopic to a different grade and rerun the script.

## Files

| File | Contents |
|---|---|
| `grade6.db` / `grade7.db` / `grade8.db` | One SQLite database per grade: `questions`, `options`, `misconceptions` tables, scoped to only that grade's content |
| `grade6_questions.csv` / `grade7_questions.csv` / `grade8_questions.csv` | Same data as flat CSVs, one row per option |
| `combined.db` | All 100 questions in one database, with a `grade` column on `questions` |
| `all_grades_questions.csv` | All 400 option-rows, with a `Grade` column |
| `split_by_grade.py` | The script that builds all of the above from `pal_fractions.db` (included) |

## Checked before packaging

- Every question in every grade file has exactly 4 options and exactly 1 correct option.
- Row counts match exactly (questions × 4).
- Each grade's `misconceptions` table only contains misconceptions actually used by that
  grade's questions (35 for grade 6, 18 for grade 7, 12 for grade 8).
- `combined.db` question counts by grade match the per-grade files (56 / 34 / 10 = 100).

## Rebuilding after you edit the grade mapping

```
python3 split_by_grade.py
```
This regenerates every file above from `pal_fractions.db`.

## Using this with the advanced (BKT) engine

The `pal_advanced` prototype currently loads one content database and one concept graph.
To make it grade-aware:
1. Give each grade its own `config/concepts_grade{N}.py` (a subset of the current graph).
2. Point `Content()` in `pal/content.py` at `grade6.db`, `grade7.db` or `grade8.db` based on
   the student's grade (stored on the `students` table).
3. Each concept's prerequisites should still resolve inside its own grade's questions - the
   current concept graph already respects this cleanly, since grade 7's concepts build on
   grade 6 fundamentals, and grade 8's word-problem concepts build on grade 7.

I did not wire this in yet since it changes the running system; say the word and I'll do it.

## Known limitation

**Grade 8 has only 10 questions across 2 subtopics** - real deployment needs a proper Grade 8
chapter (e.g. rational numbers, or fraction applications in mensuration/algebra) rather than
just "leftover word problems." Treat grade 8 here as a placeholder, not a real chapter.
