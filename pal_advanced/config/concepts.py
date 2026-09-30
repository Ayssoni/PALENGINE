"""
Concept graph for the fractions chapter.
Each concept = one subtopic in the content DB. Edges are prerequisites: a concept's
prerequisites should reach mastery before the engine focuses a student on it.
This is a teacher-editable judgement call, not derived from data.
"""

CONCEPTS = {
    "part_of_whole":        {"label": "Fraction as part of a whole", "prereqs": []},
    "num_den":              {"label": "Numerator and denominator", "prereqs": ["part_of_whole"]},
    "equal_parts":          {"label": "Equal parts", "prereqs": ["part_of_whole"]},
    "number_line":          {"label": "Fractions on a number line", "prereqs": ["num_den"]},
    "compare_unit":         {"label": "Comparing unit fractions", "prereqs": ["num_den"]},
    "equivalent":           {"label": "Equivalent fractions", "prereqs": ["num_den"]},
    "simplifying":          {"label": "Simplifying fractions", "prereqs": ["equivalent"]},
    "compare_same_num":     {"label": "Comparing fractions with the same numerator", "prereqs": ["compare_unit"]},
    "add_like":             {"label": "Adding like fractions", "prereqs": ["num_den"]},
    "sub_like":             {"label": "Subtracting like fractions", "prereqs": ["add_like"]},
    "fraction_of_qty":      {"label": "Fraction of a quantity", "prereqs": ["num_den"]},
    "compare_unlike":       {"label": "Comparing unlike fractions", "prereqs": ["equivalent", "compare_same_num"]},
    "add_unlike":           {"label": "Adding unlike fractions", "prereqs": ["equivalent", "add_like"]},
    "sub_unlike":           {"label": "Subtracting unlike fractions", "prereqs": ["add_unlike"]},
    "mixed_improper":       {"label": "Mixed numbers and improper fractions", "prereqs": ["add_like"]},
    "whole_part_remainder": {"label": "Whole, part and remainder", "prereqs": ["sub_like"]},
    "ordering":             {"label": "Ordering fractions", "prereqs": ["compare_unlike"]},
    "add_unlike_gt1":       {"label": "Adding unlike fractions (answer above 1)", "prereqs": ["add_unlike"]},
    "sub_mixed":            {"label": "Subtracting mixed numbers", "prereqs": ["mixed_improper", "sub_unlike"]},
    "multiplying":          {"label": "Multiplying fractions", "prereqs": ["simplifying"]},
    "dividing":             {"label": "Dividing fractions", "prereqs": ["multiplying"]},
    "div_whole_by_frac":    {"label": "Dividing a whole number by a fraction", "prereqs": ["dividing"]},
    "word_problems":        {"label": "Fraction word problems", "prereqs": ["add_unlike", "multiplying", "dividing"]},
    "mixed_word_problems":  {"label": "Mixed number word problems", "prereqs": ["sub_mixed"]},
}

LABEL_TO_ID = {v["label"]: k for k, v in CONCEPTS.items()}


def topo_order():
    """Concepts in an order where every prerequisite comes before its dependents."""
    order, seen = [], set()

    def visit(cid):
        if cid in seen:
            return
        seen.add(cid)
        for p in CONCEPTS[cid]["prereqs"]:
            visit(p)
        order.append(cid)

    for cid in CONCEPTS:
        visit(cid)
    return order


def prereqs_met(cid, mastery, threshold):
    return all(mastery.get(p, 0.0) >= threshold for p in CONCEPTS[cid]["prereqs"])


for _cid, _c in CONCEPTS.items():
    for _p in _c["prereqs"]:
        assert _p in CONCEPTS, f"unknown prerequisite '{_p}' for concept '{_cid}'"
assert len(topo_order()) == len(CONCEPTS), "concept graph has a cycle or a disconnected id"

