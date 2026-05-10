"""NPMI math tests."""

from __future__ import annotations

import math

import pytest

from star_crawl.graph.ppmi import npmi


@pytest.mark.unit
def test_perfectly_correlated_pair_returns_one():
    # Both keywords appear in exactly the same articles → max NPMI
    val = npmi(co_count=10, df_a=10, df_b=10, n_total=100)
    # NPMI should be close to 1 when two terms are perfectly co-occurring
    assert val == pytest.approx(1.0, abs=0.05)


@pytest.mark.unit
def test_independent_pair_returns_near_zero():
    # If P(a,b) ≈ P(a)*P(b), NPMI ≈ 0
    # P(a)=0.1, P(b)=0.1 → independent P(a,b)=0.01 → 1 article in 100
    val = npmi(co_count=1, df_a=10, df_b=10, n_total=100)
    assert val == pytest.approx(0.0, abs=0.01)


@pytest.mark.unit
def test_negative_association_clipped_to_zero():
    # Less co-occurrence than expected by chance → NPMI < 0 → clipped to 0
    val = npmi(co_count=1, df_a=50, df_b=50, n_total=100)
    assert val == 0.0


@pytest.mark.unit
def test_returns_zero_on_degenerate_inputs():
    assert npmi(0, 5, 5, 100) == 0.0
    assert npmi(5, 0, 5, 100) == 0.0
    assert npmi(5, 5, 0, 100) == 0.0
    assert npmi(5, 5, 5, 0) == 0.0


@pytest.mark.unit
def test_value_bounded_in_unit_interval():
    for c, a, b, n in [(3, 5, 5, 100), (10, 20, 20, 1000), (1, 2, 3, 50)]:
        val = npmi(c, a, b, n)
        assert 0.0 <= val <= 1.0
