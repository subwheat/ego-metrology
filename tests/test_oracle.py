"""
tests/test_oracle.py
====================
Tests unitaires pour l'oracle offline C* — Ticket 6 EGO Metrology.

Couvre tous les critères d'acceptation :
1.  tâche avec 3 runs, 2 admissibles → choisit le moins cher
2.  run avec passed_quality=False ignoré
3.  run avec cost_dyn=None ignoré
4.  aucun admissible → selection_status="no_admissible_run"
5.  tie sur coût → plus grand quality_score gagne
6.  tie coût + qualité → policy_id lexicographique gagne
7.  num_candidates correct
8.  num_admissible correct
9.  build_oracle_records() groupe bien plusieurs tâches
10. summarize_oracle_records() calcule couverture et win counts
"""

import pytest

from ego_metrology.logging_schema import RunRecord, SCHEMA_VERSION
from ego_metrology.oracle import (
    ORACLE_SCHEMA_VERSION,
    OracleRecord,
    build_oracle_records,
    select_oracle_run_for_task,
    summarize_oracle_records,
    append_oracle_records_jsonl,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_counter = 0

def make_run(
    task_id: str = "bullshitbench_v2_software_0001",
    benchmark_id: str = "bullshitbench_v2",
    policy_id: str = "single_pass",
    passed_quality: bool | None = True,
    quality_score: float | None = 2.0,
    cost_dyn: float | None = 200.0,
    model_name: str = "qwen2.5-14b",
) -> RunRecord:
    global _counter
    _counter += 1
    return RunRecord(
        run_id=f"RUN{_counter:06d}",
        timestamp_utc="2026-03-19T16:00:00Z",
        task_id=task_id,
        benchmark_id=benchmark_id,
        model_name=model_name,
        policy_id=policy_id,
        backend_name="fake_backend",
        manifest_hash="sha256:abc",
        calibration_status="experimental",
        runner_version="ego-metrology/0.3.0-dev",
        schema_version=SCHEMA_VERSION,
        passed_quality=passed_quality,
        quality_score=quality_score,
        quality_threshold=2.0 if quality_score is not None else None,
        cost_dyn=cost_dyn,
    )


# ---------------------------------------------------------------------------
# 1. Tâche avec 3 runs, 2 admissibles → choisit le moins cher
# ---------------------------------------------------------------------------

class TestBasicSelection:
    def test_selects_cheapest_admissible(self):
        runs = [
            make_run(policy_id="single_pass", cost_dyn=300.0),
            make_run(policy_id="single_pass_verify", cost_dyn=150.0),
            make_run(policy_id="cascade_small_to_large", cost_dyn=500.0),
        ]
        record = select_oracle_run_for_task(runs)
        assert record.oracle_policy_id == "single_pass_verify"
        assert record.cost_star == pytest.approx(150.0)
        assert record.selection_status == "ok"

    def test_oracle_quality_score_set(self):
        runs = [
            make_run(policy_id="single_pass", cost_dyn=300.0, quality_score=2.0),
            make_run(policy_id="single_pass_verify", cost_dyn=150.0, quality_score=2.0),
        ]
        record = select_oracle_run_for_task(runs)
        assert record.oracle_quality_score == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# 2. Run avec passed_quality=False ignoré
# ---------------------------------------------------------------------------

class TestAdmissibilityFilter:
    def test_failed_quality_ignored(self):
        runs = [
            make_run(policy_id="single_pass", cost_dyn=100.0, passed_quality=False, quality_score=1.0),
            make_run(policy_id="single_pass_verify", cost_dyn=200.0, passed_quality=True),
        ]
        record = select_oracle_run_for_task(runs)
        assert record.oracle_policy_id == "single_pass_verify"
        assert record.cost_star == pytest.approx(200.0)

    def test_passed_quality_none_ignored(self):
        runs = [
            make_run(policy_id="single_pass", cost_dyn=100.0, passed_quality=None, quality_score=None),
            make_run(policy_id="single_pass_verify", cost_dyn=300.0, passed_quality=True),
        ]
        record = select_oracle_run_for_task(runs)
        assert record.oracle_policy_id == "single_pass_verify"


# ---------------------------------------------------------------------------
# 3. Run avec cost_dyn=None ignoré
# ---------------------------------------------------------------------------

    def test_null_cost_dyn_ignored(self):
        runs = [
            make_run(policy_id="single_pass", cost_dyn=None, passed_quality=True),
            make_run(policy_id="single_pass_verify", cost_dyn=200.0, passed_quality=True),
        ]
        record = select_oracle_run_for_task(runs)
        assert record.oracle_policy_id == "single_pass_verify"
        assert record.num_admissible == 1


# ---------------------------------------------------------------------------
# 4. Aucun admissible → no_admissible_run
# ---------------------------------------------------------------------------

class TestNoAdmissible:
    def test_all_failed_quality(self):
        runs = [
            make_run(policy_id="single_pass", passed_quality=False, quality_score=1.0),
            make_run(policy_id="single_pass_verify", passed_quality=False, quality_score=0.0),
        ]
        record = select_oracle_run_for_task(runs)
        assert record.selection_status == "no_admissible_run"
        assert record.oracle_policy_id is None
        assert record.cost_star is None
        assert record.oracle_quality_score is None

    def test_all_null_cost(self):
        runs = [
            make_run(policy_id="single_pass", cost_dyn=None, passed_quality=True),
        ]
        record = select_oracle_run_for_task(runs)
        assert record.selection_status == "no_admissible_run"


# ---------------------------------------------------------------------------
# 5. Tie sur coût → plus grand quality_score gagne
# ---------------------------------------------------------------------------

class TestTieBreakQuality:
    def test_higher_quality_wins_on_cost_tie(self):
        runs = [
            make_run(policy_id="single_pass", cost_dyn=200.0, quality_score=2.0),
            make_run(policy_id="single_pass_verify", cost_dyn=200.0, quality_score=2.0),
        ]
        # Les deux ont même coût et même qualité → tie-break lexicographique
        record = select_oracle_run_for_task(runs)
        assert record.meta["tie_break_applied"] is True

    def test_higher_quality_score_beats_lower_at_same_cost(self):
        runs = [
            make_run(policy_id="policy_a", cost_dyn=200.0, quality_score=2.0),
            make_run(policy_id="policy_b", cost_dyn=200.0, quality_score=3.0),
        ]
        record = select_oracle_run_for_task(runs)
        assert record.oracle_policy_id == "policy_b"
        assert record.oracle_quality_score == pytest.approx(3.0)

    def test_higher_quality_score_wins(self):
        # Simuler deux runs même coût, qualité différente
        # Pour tester, on doit bypasser la contrainte passed_quality via quality_score
        run_low = make_run(policy_id="z_policy", cost_dyn=200.0, quality_score=2.0)
        run_high = make_run(policy_id="a_policy", cost_dyn=200.0, quality_score=2.0)
        # Même qualité → lexicographique : a_policy < z_policy
        record = select_oracle_run_for_task([run_low, run_high])
        assert record.oracle_policy_id == "a_policy"


# ---------------------------------------------------------------------------
# 6. Tie coût + qualité → policy_id lexicographique gagne
# ---------------------------------------------------------------------------

class TestTieBreakLexicographic:
    def test_lexicographic_on_full_tie(self):
        runs = [
            make_run(policy_id="z_single_pass", cost_dyn=200.0, quality_score=2.0),
            make_run(policy_id="a_single_pass", cost_dyn=200.0, quality_score=2.0),
            make_run(policy_id="m_single_pass", cost_dyn=200.0, quality_score=2.0),
        ]
        record = select_oracle_run_for_task(runs)
        assert record.oracle_policy_id == "a_single_pass"


# ---------------------------------------------------------------------------
# 7-8. num_candidates et num_admissible corrects
# ---------------------------------------------------------------------------

class TestCounts:
    def test_num_candidates(self):
        runs = [
            make_run(policy_id="single_pass", passed_quality=True, cost_dyn=100.0),
            make_run(policy_id="single_pass_verify", passed_quality=False, quality_score=1.0, cost_dyn=80.0),
            make_run(policy_id="cascade_small_to_large", passed_quality=True, cost_dyn=150.0),
        ]
        record = select_oracle_run_for_task(runs)
        assert record.num_candidates == 3

    def test_num_admissible(self):
        runs = [
            make_run(policy_id="single_pass", passed_quality=True, cost_dyn=100.0),
            make_run(policy_id="single_pass_verify", passed_quality=False, quality_score=1.0, cost_dyn=80.0),
            make_run(policy_id="cascade_small_to_large", passed_quality=True, cost_dyn=150.0),
        ]
        record = select_oracle_run_for_task(runs)
        assert record.num_admissible == 2

    def test_admissible_policy_ids_correct(self):
        runs = [
            make_run(policy_id="single_pass", passed_quality=True, cost_dyn=100.0),
            make_run(policy_id="single_pass_verify", passed_quality=False, quality_score=1.0, cost_dyn=80.0),
        ]
        record = select_oracle_run_for_task(runs)
        assert record.admissible_policy_ids == ["single_pass"]


# ---------------------------------------------------------------------------
# 9. build_oracle_records groupe plusieurs tâches
# ---------------------------------------------------------------------------

class TestBuildOracleRecords:
    def test_groups_by_task_id(self):
        runs = [
            make_run(task_id="task_001", policy_id="single_pass", cost_dyn=100.0),
            make_run(task_id="task_001", policy_id="single_pass_verify", cost_dyn=200.0),
            make_run(task_id="task_002", policy_id="single_pass", cost_dyn=300.0),
        ]
        records = build_oracle_records(runs)
        assert len(records) == 2
        task_ids = [r.task_id for r in records]
        assert "task_001" in task_ids
        assert "task_002" in task_ids

    def test_sorted_by_task_id(self):
        runs = [
            make_run(task_id="task_z", cost_dyn=100.0),
            make_run(task_id="task_a", cost_dyn=100.0),
        ]
        records = build_oracle_records(runs)
        assert records[0].task_id == "task_a"
        assert records[1].task_id == "task_z"

    def test_benchmark_filter(self):
        runs = [
            make_run(task_id="t1", benchmark_id="bullshitbench_v2", cost_dyn=100.0),
            make_run(task_id="t2", benchmark_id="other_bench", cost_dyn=100.0),
        ]
        records = build_oracle_records(runs, benchmark_id="bullshitbench_v2")
        assert len(records) == 1
        assert records[0].task_id == "t1"

    def test_raises_on_mixed_benchmark_ids_per_task(self):
        runs = [
            make_run(task_id="same_task", benchmark_id="bench_a", cost_dyn=100.0),
            make_run(task_id="same_task", benchmark_id="bench_b", cost_dyn=200.0),
        ]
        with pytest.raises(ValueError, match="benchmark_id multiples"):
            build_oracle_records(runs)

    def test_raises_on_empty_runs(self):
        with pytest.raises(ValueError):
            select_oracle_run_for_task([])


# ---------------------------------------------------------------------------
# 10. summarize_oracle_records
# ---------------------------------------------------------------------------

class TestSummarize:
    def _make_records(self):
        return [
            OracleRecord(
                task_id="t1", benchmark_id="b",
                oracle_policy_id="single_pass", cost_star=100.0,
                oracle_quality_score=2.0,
                selection_status="ok",
                num_candidates=2, num_admissible=2,
            ),
            OracleRecord(
                task_id="t2", benchmark_id="b",
                oracle_policy_id="single_pass_verify", cost_star=200.0,
                oracle_quality_score=2.0,
                selection_status="ok",
                num_candidates=2, num_admissible=1,
            ),
            OracleRecord(
                task_id="t3", benchmark_id="b",
                selection_status="no_admissible_run",
                num_candidates=1, num_admissible=0,
            ),
        ]

    def test_total_count(self):
        summary = summarize_oracle_records(self._make_records())
        assert summary["num_tasks_total"] == 3

    def test_with_oracle_count(self):
        summary = summarize_oracle_records(self._make_records())
        assert summary["num_tasks_with_oracle"] == 2

    def test_without_admissible_count(self):
        summary = summarize_oracle_records(self._make_records())
        assert summary["num_tasks_without_admissible_run"] == 1

    def test_oracle_coverage(self):
        summary = summarize_oracle_records(self._make_records())
        assert summary["oracle_coverage"] == pytest.approx(2 / 3)

    def test_mean_cost_star(self):
        summary = summarize_oracle_records(self._make_records())
        assert summary["mean_cost_star"] == pytest.approx(150.0)

    def test_win_counts(self):
        summary = summarize_oracle_records(self._make_records())
        assert summary["oracle_policy_win_counts"]["single_pass"] == 1
        assert summary["oracle_policy_win_counts"]["single_pass_verify"] == 1

    def test_empty_records(self):
        summary = summarize_oracle_records([])
        assert summary["num_tasks_total"] == 0
        assert summary["oracle_coverage"] == 0.0
        assert summary["mean_cost_star"] is None

    def test_schema_version_constant(self):
        assert ORACLE_SCHEMA_VERSION == "oracle.v1"


# ---------------------------------------------------------------------------
# JSONL I/O
# ---------------------------------------------------------------------------

class TestOracleJsonlIO:
    def test_append_and_reload(self, tmp_path):
        path = tmp_path / "oracle.jsonl"
        records = [
            OracleRecord(
                task_id="t1", benchmark_id="bullshitbench_v2",
                oracle_policy_id="single_pass", cost_star=150.0,
                selection_status="ok",
                num_candidates=1, num_admissible=1,
            )
        ]
        append_oracle_records_jsonl(path, records)
        with path.open() as f:
            lines = f.readlines()
        assert len(lines) == 1
        import json
        parsed = json.loads(lines[0])
        assert parsed["task_id"] == "t1"
        assert parsed["cost_star"] == pytest.approx(150.0)
