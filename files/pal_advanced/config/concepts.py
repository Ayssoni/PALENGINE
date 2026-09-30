"""
Concept graph for the fractions chapters, grades 6-8.
Each concept = one subtopic in the content DB, tagged with the grade it belongs to and its
prerequisites. A prerequisite from an EARLIER grade is assumed already known by the time a
student reaches this grade (they passed that grade), so grade-scoped graphs (see
get_grade_concepts) drop those and gate only on same-grade prerequisites.
This is a teacher-editable curriculum judgement call, not derived from data.
"""

CONCEPTS = {
    "part_of_whole":        {"label": "Fraction as part of a whole", "grade": 6, "prereqs": []},
    "num_den":              {"label": "Numerator and denominator", "grade": 6, "prereqs": ["part_of_whole"]},
    "equal_parts":          {"label": "Equal parts", "grade": 6, "prereqs": ["part_of_whole"]},
    "number_line":          {"label": "Fractions on a number line", "grade": 6, "prereqs": ["num_den"]},
    "compare_unit":         {"label": "Comparing unit fractions", "grade": 6, "prereqs": ["num_den"]},
    "equivalent":           {"label": "Equivalent fractions", "grade": 6, "prereqs": ["num_den"]},
    "simplifying":          {"label": "Simplifying fractions", "grade": 6, "prereqs": ["equivalent"]},
    "compare_same_num":     {"label": "Comparing fractions with the same numerator", "grade": 6, "prereqs": ["compare_unit"]},
    "add_like":             {"label": "Adding like fractions", "grade": 6, "prereqs": ["num_den"]},
    "sub_like":             {"label": "Subtracting like fractions", "grade": 6, "prereqs": ["add_like"]},
    "fraction_of_qty":      {"label": "Fraction of a quantity", "grade": 6, "prereqs": ["num_den"]},
    "compare_unlike":       {"label": "Comparing unlike fractions", "grade": 6, "prereqs": ["equivalent", "compare_same_num"]},
    "whole_part_remainder": {"label": "Whole, part and remainder", "grade": 6, "prereqs": ["sub_like"]},
    "ordering":             {"label": "Ordering fractions", "grade": 6, "prereqs": ["compare_unlike"]},

    "add_unlike":           {"label": "Adding unlike fractions", "grade": 7, "prereqs": ["equivalent", "add_like"]},
    "sub_unlike":           {"label": "Subtracting unlike fractions", "grade": 7, "prereqs": ["add_unlike"]},
    "mixed_improper":       {"label": "Mixed numbers and improper fractions", "grade": 7, "prereqs": ["add_like"]},
    "add_unlike_gt1":       {"label": "Adding unlike fractions (answer above 1)", "grade": 7, "prereqs": ["add_unlike"]},
    "sub_mixed":            {"label": "Subtracting mixed numbers", "grade": 7, "prereqs": ["mixed_improper", "sub_unlike"]},
    "multiplying":          {"label": "Multiplying fractions", "grade": 7, "prereqs": ["simplifying"]},
    "dividing":             {"label": "Dividing fractions", "grade": 7, "prereqs": ["multiplying"]},
    "div_whole_by_frac":    {"label": "Dividing a whole number by a fraction", "grade": 7, "prereqs": ["dividing"]},

    "word_problems":        {"label": "Fraction word problems", "grade": 8, "prereqs": ["add_unlike", "multiplying", "dividing"]},
    "mixed_word_problems":  {"label": "Mixed number word problems", "grade": 8, "prereqs": ["sub_mixed"]},
}

LABEL_TO_ID = {v["label"]: k for k, v in CONCEPTS.items()}
GRADES = (6, 7, 8)


def topo_order(concepts=CONCEPTS):
    """Concepts in an order where every prerequisite (within `concepts`) comes before its dependents."""
    order, seen = [], set()

    def visit(cid):
        if cid in seen:
            return
        seen.add(cid)
        for p in concepts[cid]["prereqs"]:
            if p in concepts:          # prereqs outside this subgraph are not walked
                visit(p)
        order.append(cid)

    for cid in concepts:
        visit(cid)
    return order


def get_grade_concepts(grade):
    """
    A grade-scoped copy of the graph: only this grade's concepts, and each concept's
    prerequisites filtered down to ones also in this grade. A prerequisite from an earlier
    grade (e.g. grade 7's 'add_unlike' depends on grade 6's 'equivalent') is dropped here -
    a student entering grade 7 is assumed to already have it, so within THIS grade's engine
    there is nothing left to gate on for that prerequisite.
    """
    subset = {cid: c for cid, c in CONCEPTS.items() if c["grade"] == grade}
    return {cid: {**c, "prereqs": [p for p in c["prereqs"] if p in subset]} for cid, c in subset.items()}


def prereqs_met(cid, mastery, threshold, concepts=CONCEPTS):
    return all(mastery.get(p, 0.0) >= threshold for p in concepts[cid]["prereqs"])


for _cid, _c in CONCEPTS.items():
    for _p in _c["prereqs"]:
        assert _p in CONCEPTS, f"unknown prerequisite '{_p}' for concept '{_cid}'"
        assert CONCEPTS[_p]["grade"] <= _c["grade"], (
            f"'{_cid}' (grade {_c['grade']}) lists a LATER-grade prerequisite '{_p}' (grade {CONCEPTS[_p]['grade']})")
assert len(topo_order()) == len(CONCEPTS), "concept graph has a cycle or a disconnected id"
for _g in GRADES:
    assert get_grade_concepts(_g), f"grade {_g} has no concepts"


