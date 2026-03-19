"""
tests/test_cost.py
==================
Tests unitaires pour cost_dyn v1 — Ticket 3 EGO Metrology.

Couvre tous les critères d'acceptation :
1.  calcul nominal
2.  zéros
3.  total_tokens None → None
4.  latency_ms None → None
5.  tokens négatifs → erreur
6.  latence négative → erreur
7.  poids négatifs → erreur
8.  compute_cost_dyn_from_run lit les champs RunRecord
9.  with_computed_cost_dyn retourne un nouveau record enrichi
10. overwrite=False conserve cost_dyn existant
11. overwrite=True recalcule
12. constantes v1 stables
"""

import pytest

from ego_metrology.cost import (
    COST_DYN_SCHEMA_VERSION,
    DEFAULT_W_LATENCY,
    DEFAULT_W_TOKENS,
    compute_cost_dyn,
    compute_cost_dyn_from_run,
    with_computed_cost_dyn,
)
from ego_metrology.logging_schema import RunRecord, SCHEMA_VERSION

# ---------------------------------------------------------------------------
# Fixture RunRecord minimal
# ---------------------------------------------------------------------------

BASE_KWARGS = dict(
    run_id="TEST001",
    timestamp_utc="2026-03-19T16:42:31Z",
    task_id="task_001",
    benchmark_id="bench_a",
    model_name="qwen2.5-14b",
    policy_id="single_pass",
    backend_name="local_vllm",
    manifest_hash="sha256:abc123",
    calibration_status="experimental",
    runner_version="ego-metrology/0.3.0-dev",
    schema_version=SCHEMA_VERSION,
)


def make_record(**kwargs) -> RunRecord:
    return RunRecord(**{**BASE_KWARGS, **kwargs})


# ---------------------------------------------------------------------------
# 1-2. Calculs nominaux
# ---------------------------------------------------------------------------

class TestComputeCostDyn:
    def test_nominal(self):
        result = compute_cost_dyn(total_tokens=100, latency_ms=500)
        assert result == pytest.approx(100.5)

    def test_canonical_example(self):
        result = compute_cost_dyn(total_tokens=935, latency_ms=1842.6)
        assert result == pytest.approx(936.8426)

    def test_zeros(self):
        assert compute_cost_dyn(total_tokens=0, latency_ms=0) == pytest.approx(0.0)

    def test_only_tokens(self):
        # latency_ms=0 → cost = tokens seuls
        result = compute_cost_dyn(total_tokens=500, latency_ms=0)
        assert result == pytest.approx(500.0)

    def test_custom_weights(self):
        result = compute_cost_dyn(total_tokens=100, latency_ms=1000, w_tokens=2.0, w_latency=0.01)
        assert result == pytest.approx(210.0)


# ---------------------------------------------------------------------------
# 3-4. Données manquantes → None
# ---------------------------------------------------------------------------

class TestMissingData:
    def test_total_tokens_none(self):
        assert compute_cost_dyn(total_tokens=None, latency_ms=500) is None

    def test_latency_ms_none(self):
        assert compute_cost_dyn(total_tokens=100, latency_ms=None) is None

    def test_both_none(self):
        assert compute_cost_dyn(total_tokens=None, latency_ms=None) is None


# ---------------------------------------------------------------------------
# 5-7. Valeurs négatives → erreur
# ---------------------------------------------------------------------------

class TestNegativeValues:
    def test_negative_tokens_raises(self):
        with pytest.raises(ValueError, match="total_tokens"):
            compute_cost_dyn(total_tokens=-1, latency_ms=500)

    def test_negative_latency_raises(self):
        with pytest.raises(ValueError, match="latency_ms"):
            compute_cost_dyn(total_tokens=100, latency_ms=-1.0)

    def test_negative_w_tokens_raises(self):
        with pytest.raises(ValueError, match="w_tokens"):
            compute_cost_dyn(total_tokens=100, latency_ms=500, w_tokens=-1.0)

    def test_negative_w_latency_raises(self):
        with pytest.raises(ValueError, match="w_latency"):
            compute_cost_dyn(total_tokens=100, latency_ms=500, w_latency=-0.001)


# ---------------------------------------------------------------------------
# 8. compute_cost_dyn_from_run
# ---------------------------------------------------------------------------

class TestFromRun:
    def test_reads_record_fields(self):
        record = make_record(total_tokens=935, latency_ms=1842.6)
        result = compute_cost_dyn_from_run(record)
        assert result == pytest.approx(936.8426)

    def test_returns_none_if_tokens_missing(self):
        record = make_record(latency_ms=1000.0)
        assert compute_cost_dyn_from_run(record) is None

    def test_returns_none_if_latency_missing(self):
        record = make_record(total_tokens=500)
        assert compute_cost_dyn_from_run(record) is None

    def test_returns_none_if_both_missing(self):
        record = make_record()
        assert compute_cost_dyn_from_run(record) is None


# ---------------------------------------------------------------------------
# 9-11. with_computed_cost_dyn
# ---------------------------------------------------------------------------

class TestWithComputedCostDyn:
    def test_enriches_record(self):
        record = make_record(total_tokens=935, latency_ms=1842.6)
        enriched = with_computed_cost_dyn(record)
        assert enriched.cost_dyn == pytest.approx(936.8426)

    def test_does_not_mutate_original(self):
        record = make_record(total_tokens=935, latency_ms=1842.6)
        enriched = with_computed_cost_dyn(record)
        assert record.cost_dyn is None
        assert enriched is not record

    def test_overwrite_false_preserves_existing(self):
        record = make_record(total_tokens=935, latency_ms=1842.6, cost_dyn=999.0)
        enriched = with_computed_cost_dyn(record, overwrite=False)
        assert enriched.cost_dyn == pytest.approx(999.0)

    def test_overwrite_true_recalculates(self):
        record = make_record(total_tokens=935, latency_ms=1842.6, cost_dyn=999.0)
        enriched = with_computed_cost_dyn(record, overwrite=True)
        assert enriched.cost_dyn == pytest.approx(936.8426)

    def test_returns_none_cost_if_data_missing(self):
        record = make_record()
        enriched = with_computed_cost_dyn(record)
        assert enriched.cost_dyn is None


# ---------------------------------------------------------------------------
# 12. Constantes v1 stables
# ---------------------------------------------------------------------------

class TestConstants:
    def test_schema_version(self):
        assert COST_DYN_SCHEMA_VERSION == "cost-dyn.v1"

    def test_default_w_tokens(self):
        assert DEFAULT_W_TOKENS == 1.0

    def test_default_w_latency(self):
        assert DEFAULT_W_LATENCY == 0.001
