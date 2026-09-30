"""
Bayesian Knowledge Tracing (BKT).

State: P(L) - the probability the student has mastered the skill (concept), before seeing
the evidence from the current question.

Parameters per concept:
    p_init    P(L0)  - prior probability of mastery before any evidence
    p_transit P(T)   - probability of moving from not-mastered to mastered after one opportunity
    p_guess   P(G)   - probability of a correct answer despite not having mastered the skill
    p_slip    P(S)   - probability of a wrong answer despite having mastered the skill

Update (standard BKT, Corbett & Anderson 1994):
    1. Bayes update using the observed correctness:
         if correct:   P(L | correct) = P(L)(1-S) / [ P(L)(1-S) + (1-P(L))G ]
         if incorrect: P(L | wrong)   = P(L)S     / [ P(L)S     + (1-P(L))(1-G) ]
    2. Apply learning (the "no forgetting" assumption of classic BKT):
         P(L') = P(L|evidence) + (1 - P(L|evidence)) * T
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class BKTParams:
    p_init: float = 0.30      # with a 4-option MCQ, start neutral-low; the questions themselves confirm it fast
    p_transit: float = 0.15
    p_guess: float = 0.22     # a bit below the naive 0.25, since some distractors are more tempting than random
    p_slip: float = 0.10


DEFAULT_PARAMS = BKTParams()
MASTERY_THRESHOLD = 0.80   # concept is considered "mastered" for prerequisite-gating and difficulty choice


def update(p_l, correct: bool, params: BKTParams = DEFAULT_PARAMS) -> float:
    """One BKT update step. p_l is P(L) before this observation."""
    g, s, t = params.p_guess, params.p_slip, params.p_transit
    p_l = min(max(p_l, 1e-6), 1 - 1e-6)
    if correct:
        num = p_l * (1 - s)
        den = p_l * (1 - s) + (1 - p_l) * g
    else:
        num = p_l * s
        den = p_l * s + (1 - p_l) * (1 - g)
    p_post_evidence = num / den if den > 0 else p_l
    p_l_new = p_post_evidence + (1 - p_post_evidence) * t
    return min(max(p_l_new, 0.0), 1.0)


def predict_correct(p_l, params: BKTParams = DEFAULT_PARAMS) -> float:
    """P(next answer on this concept is correct), given current mastery belief."""
    return p_l * (1 - params.p_slip) + (1 - p_l) * params.p_guess


def to_pct(p_l) -> float:
    return round(p_l * 100, 1)
