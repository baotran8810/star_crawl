"""Normalized Pointwise Mutual Information."""

from __future__ import annotations

import math


def npmi(co_count: int, df_a: int, df_b: int, n_total: int) -> float:
    """Compute NPMI for a pair.

    NPMI(a,b) = PMI(a,b) / -log(p(a,b))
              = log(p(a,b) / (p(a) p(b))) / -log(p(a,b))

    Returns 0.0 (clipped from negative) when association is below independence,
    or when any input is degenerate.
    """
    if co_count <= 0 or df_a <= 0 or df_b <= 0 or n_total <= 0:
        return 0.0
    p_ab = co_count / n_total
    p_a = df_a / n_total
    p_b = df_b / n_total
    if p_ab <= 0 or p_ab >= 1.0:
        return 0.0
    pmi = math.log(p_ab / (p_a * p_b))
    denom = -math.log(p_ab)
    if denom <= 0:
        return 0.0
    val = pmi / denom
    return max(0.0, min(1.0, val))
