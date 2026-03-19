"""
tests/test_regret.py
====================
Tests unitaires pour routing_regret v1 — Ticket 7 EGO Metrology.

Couvre tous les critères d'acceptation :
1.  regret nominal : chosen=120, cost_star=100 → 20
2.  regret nul : chosen=100, cost_star=100 → 0
3.  oracle absent → no_oracle
4.  cost_star=None → no_oracle
5.  chosen_run.cost_dyn=None → chosen_cost_missing
6.  benchmark mismatch → benchmark_mismatch
7.  regret négatif conservé
8.  oracle_match_rate correct
9.  chosen_policy_counts correct
10. build_regret_records associe bien par task_id
"""

import pytest

from ego_metrology.logging_schema import RunRecord, SCHEMA_VERSION
from ego_metrology.oracle import OracleRecord
from ego_metrology.regret import (
    REGRET_SCHEMA_VERSION,
    RegretRecord,
    build_regret_records,
    compute_routing_regret,
    make_regret_record,
    summarize_regret_records,
    append_regret_records_jsonl,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_counter = 0


def make_run(
    task_id: str = "bullshitbench_v2_software_0001",
    benchmark_id: str = "bullshitbench_v2",
    policy_id: str = "single_pass",
    cost_dyn: float | None = 200.0,
    passed_quality: bool | None = True,
    quality_score: float | None = 2.0,
) -> RunRecord:
    global _counter
    _counter += 1
    return RunRecord(
        run_id=f"RUN{_counter:06d}",
        timestamp_utc="2026-03-19T16:00:00Z",
        task_id=task_id,
        benchmark_id=benchmark_id,
        model_name="qwen2.5-14b",
        policy_id=policy_id,
        backend_name="fake_backend",
        manifest_hash="sha256:abc",
        calibration_status="experimental",
        runner_version="ego-metrology/0.3.0-dev",
        schema_version=SCHEMA_VERSION,
        cost_dyn=cost_dyn,
        passed_quality=passed_quality,
        quality_score=quality_score,
        quality_threshold=2.0 if quality_score is not None else None,
    )


def make_oracle(
    task_id: str = "bullshitbench_v2_software_0001",
    benchmark_id: str = "bullshitbench_v2",
    oracle_policy_id: str | None = "single_pass",
    cost_star: float | None = 100.0,
    selection_status: str = "ok",
) -> OracleRecord:
    return OracleRecord(
        task_id=task_id,
        benchmark_id=benchmark_id,
        oracle_policy_id=oracle_policy_id,
        cost_star=cost_star,
        selection_status=selection_status,
        num_candidates=1,
        num_admissible=1,
    )


# ---------------------------------------------------------------------------
# compute_routing_regret — fonction pure
# ---------------------------------------------------------------------------

class TestComputeRoutingRegret:
    def test_nominal(self):
        assert compute_routing_regret(chosen_cost_dyn=120.0, cost_star=100.0) == pytest.approx(20.0)

    def test_zero(self):
        assert compute_routing_regret(chosen_cost_dyn=100.0, cost_star=100.0) == pytest.approx(0.0)

    def test_negative(self):
        assert compute_routing_regret(chosen_cost_dyn=80.0, cost_star=100.0) == pytest.approx(-20.0)

    def test_chosen_none(self):
        assert compute_routing_regret(chosen_cost_dyn=None, cost_star=100.0) is None

    def test_star_none(self):
        assert compute_routing_regret(chosen_cost_dyn=120.0, cost_star=None) is None

    def test_both_none(self):
        assert compute_routing_regret(chosen_cost_dyn=None, cost_star=None) is None


# ---------------------------------------------------------------------------
# 1-2. Regret nominal et nul
# ---------------------------------------------------------------------------

class TestNominalRegret:
    def test_nominal_regret(self):
        run = make_run(cost_dyn=120.0, policy_id="single_pass_verify")
        oracle = make_oracle(cost_star=100.0, oracle_policy_id="single_pass")
        record = make_regret_record(run, oracle)
        assert record.routing_regret == pytest.approx(20.0)
        assert record.regret_status == "ok"
        assert record.oracle_available is True

    def test_zero_regret(self):
        run = make_run(cost_dyn=100.0, policy_id="single_pass")
        oracle = make_oracle(cost_star=100.0, oracle_policy_id="single_pass")
        record = make_regret_record(run, oracle)
        assert record.routing_regret == pytest.approx(0.0)
        assert record.regret_status == "ok"

    def test_chosen_and_oracle_policy_same(self):
        run = make_run(cost_dyn=100.0, policy_id="single_pass")
        oracle = make_oracle(cost_star=100.0, oracle_policy_id="single_pass")
        record = make_regret_record(run, oracle)
        assert record.meta["delta_vs_oracle_policy"] == "same_policy"

    def test_chosen_and_oracle_policy_different(self):
        run = make_run(cost_dyn=200.0, policy_id="single_pass_verify")
        oracle = make_oracle(cost_star=100.0, oracle_policy_id="single_pass")
        record = make_regret_record(run, oracle)
        assert record.meta["delta_vs_oracle_policy"] == "different_policy"


# ---------------------------------------------------------------------------
# 3. Oracle absent → no_oracle
# ---------------------------------------------------------------------------

class TestNoOracle:
    def test_oracle_none(self):
        run = make_run(cost_dyn=200.0)
        record = make_regret_record(run, None)
        assert record.regret_status == "no_oracle"
        assert record.routing_regret is None
        assert record.oracle_available is False

    def test_cost_star_none(self):
        run = make_run(cost_dyn=200.0)
        oracle = make_oracle(cost_star=None, selection_status="no_admissible_run")
        record = make_regret_record(run, oracle)
        assert record.regret_status == "no_oracle"
        assert record.routing_regret is None

    def test_oracle_status_not_ok(self):
        run = make_run(cost_dyn=200.0)
        oracle = make_oracle(cost_star=100.0, selection_status="no_admissible_run")
        record = make_regret_record(run, oracle)
        assert record.regret_status == "no_oracle"


# ---------------------------------------------------------------------------
# 5. chosen_run.cost_dyn=None → chosen_cost_missing
# ---------------------------------------------------------------------------

class TestChosenCostMissing:
    def test_null_cost_dyn(self):
        run = make_run(cost_dyn=None)
        oracle = make_oracle(cost_star=100.0)
        record = make_regret_record(run, oracle)
        assert record.regret_status == "chosen_cost_missing"
        assert record.routing_regret is None
        assert record.oracle_available is True
        assert record.cost_star == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# 6. Benchmark mismatch
# ---------------------------------------------------------------------------

class TestBenchmarkMismatch:
    def test_different_benchmark_ids(self):
        run = make_run(benchmark_id="bullshitbench_v2")
        oracle = make_oracle(benchmark_id="other_bench")
        record = make_regret_record(run, oracle)
        assert record.regret_status == "benchmark_mismatch"
        assert record.routing_regret is None
        assert record.oracle_available is False


# ---------------------------------------------------------------------------
# 7. Regret négatif conservé
# ---------------------------------------------------------------------------

class TestNegativeRegret:
    def test_negative_regret_preserved(self):
        run = make_run(cost_dyn=80.0)
        oracle = make_oracle(cost_star=100.0)
        record = make_regret_record(run, oracle)
        assert record.routing_regret == pytest.approx(-20.0)
        assert record.regret_status == "ok"
        assert record.meta["negative_regret_detected"] is True


# ---------------------------------------------------------------------------
# 9. chosen_policy_counts et oracle_match_rate
# ---------------------------------------------------------------------------

class TestSummary:
    def _make_records(self):
        return [
            RegretRecord(
                task_id="t1", benchmark_id="b",
                chosen_policy_id="single_pass",
                oracle_policy_id="single_pass",
                chosen_cost_dyn=100.0, cost_star=100.0,
                routing_regret=0.0,
                oracle_available=True, regret_status="ok",
            ),
            RegretRecord(
                task_id="t2", benchmark_id="b",
                chosen_policy_id="single_pass_verify",
                oracle_policy_id="single_pass",
                chosen_cost_dyn=200.0, cost_star=100.0,
                routing_regret=100.0,
                oracle_available=True, regret_status="ok",
            ),
            RegretRecord(
                task_id="t3", benchmark_id="b",
                chosen_policy_id="single_pass",
                oracle_policy_id=None,
                oracle_available=False, regret_status="no_oracle",
            ),
        ]

    def test_total_count(self):
        summary = summarize_regret_records(self._make_records())
        assert summary["num_records_total"] == 3

    def test_computable_count(self):
        summary = summarize_regret_records(self._make_records())
        assert summary["num_regret_computable"] == 2

    def test_no_oracle_count(self):
        summary = summarize_regret_records(self._make_records())
        assert summary["num_no_oracle"] == 1

    def test_mean_regret(self):
        summary = summarize_regret_records(self._make_records())
        assert summary["mean_routing_regret"] == pytest.approx(50.0)

    def test_oracle_match_rate(self):
        summary = summarize_regret_records(self._make_records())
        # 1 match sur 2 computable
        assert summary["oracle_match_rate"] == pytest.approx(0.5)

    def test_chosen_policy_counts(self):
        summary = summarize_regret_records(self._make_records())
        assert summary["chosen_policy_counts"]["single_pass"] == 2
        assert summary["chosen_policy_counts"]["single_pass_verify"] == 1

    def test_zero_regret_count(self):
        summary = summarize_regret_records(self._make_records())
        assert summary["num_zero_regret"] == 1

    def test_empty_records(self):
        summary = summarize_regret_records([])
        assert summary["num_records_total"] == 0
        assert summary["mean_routing_regret"] is None
        assert summary["oracle_match_rate"] is None

    def test_schema_version_constant(self):
        assert REGRET_SCHEMA_VERSION == "routing-regret.v1"


# ---------------------------------------------------------------------------
# 10. build_regret_records
# ---------------------------------------------------------------------------

class TestBuildRegretRecords:
    def test_associates_by_task_id(self):
        runs = [
            make_run(task_id="task_001", cost_dyn=200.0, policy_id="single_pass_verify"),
            make_run(task_id="task_002", cost_dyn=150.0, policy_id="single_pass"),
        ]
        oracles = [
            make_oracle(task_id="task_001", cost_star=100.0),
            make_oracle(task_id="task_002", cost_star=150.0),
        ]
        records = build_regret_records(runs, oracles)
        assert len(records) == 2
        r1 = next(r for r in records if r.task_id == "task_001")
        assert r1.routing_regret == pytest.approx(100.0)
        r2 = next(r for r in records if r.task_id == "task_002")
        assert r2.routing_regret == pytest.approx(0.0)

    def test_sorted_by_task_id(self):
        runs = [
            make_run(task_id="task_z", cost_dyn=100.0),
            make_run(task_id="task_a", cost_dyn=100.0),
        ]
        oracles = [
            make_oracle(task_id="task_z"),
            make_oracle(task_id="task_a"),
        ]
        records = build_regret_records(runs, oracles)
        assert records[0].task_id == "task_a"
        assert records[1].task_id == "task_z"

    def test_no_oracle_for_task(self):
        runs = [make_run(task_id="task_orphan", cost_dyn=200.0)]
        records = build_regret_records(runs, [])
        assert records[0].regret_status == "no_oracle"

    def test_task_id_mismatch_raises(self):
        run = make_run(task_id="task_001", cost_dyn=200.0)
        oracle = make_oracle(task_id="task_999", cost_star=100.0)
        with pytest.raises(ValueError, match="task_id incompatible"):
            make_regret_record(run, oracle)

    def test_duplicate_oracle_task_id_raises(self):
        runs = [make_run(task_id="task_001", cost_dyn=200.0)]
        oracles = [
            make_oracle(task_id="task_001", cost_star=100.0),
            make_oracle(task_id="task_001", cost_star=90.0),
        ]
        with pytest.raises(ValueError, match="dupliqué"):
            build_regret_records(runs, oracles)


# ---------------------------------------------------------------------------
# JSONL I/O
# ---------------------------------------------------------------------------

class TestRegretJsonlIO:
    def test_append_and_read(self, tmp_path):
        path = tmp_path / "regret.jsonl"
        records = [
            RegretRecord(
                task_id="t1", benchmark_id="b",
                chosen_policy_id="single_pass",
                chosen_cost_dyn=200.0, cost_star=100.0,
                routing_regret=100.0,
                oracle_available=True, regret_status="ok",
            )
        ]
        append_regret_records_jsonl(path, records)
        with path.open() as f:
            lines = f.readlines()
        assert len(lines) == 1
        import json
        parsed = json.loads(lines[0])
        assert parsed["routing_regret"] == pytest.approx(100.0)
        assert parsed["schema_version"] == REGRET_SCHEMA_VERSION
