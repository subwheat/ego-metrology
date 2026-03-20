"""
tests/test_reporting.py
=======================
Tests unitaires pour le rapport de sprint — Ticket 8 EGO Metrology.

Couvre tous les critères d'acceptation :
1.  agrège correctement 2 politiques avec runs multiples
2.  calcule quality_pass_rate
3.  calcule mean_cost_dyn
4.  fusionne correctement les regrets par chosen_policy_id
5.  garde None si aucun regret calculable
6.  choisit la bonne politique recommandée selon la règle
7.  tie sur qualité → regret départage
8.  tie sur qualité + regret → coût départage
9.  render_markdown_report contient la politique recommandée
10. write_policy_summary_csv écrit un CSV valide
"""

import csv

import pytest

from ego_metrology.logging_schema import RunRecord, SCHEMA_VERSION
from ego_metrology.regret import RegretRecord
from ego_metrology.reporting import (
    REPORTING_SCHEMA_VERSION,
    PolicySummaryRecord,
    build_policy_summary_records,
    render_markdown_report,
    summarize_sprint_outcome,
    write_policy_summary_csv,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_counter = 0


def make_run(
    policy_id: str = "single_pass",
    benchmark_id: str = "bullshitbench_v2",
    task_id: str = "task_001",
    passed_quality: bool | None = True,
    quality_score: float | None = 2.0,
    cost_dyn: float | None = 200.0,
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
        passed_quality=passed_quality,
        quality_score=quality_score,
        quality_threshold=2.0 if quality_score is not None else None,
        cost_dyn=cost_dyn,
    )


def make_regret(
    chosen_policy_id: str = "single_pass",
    benchmark_id: str = "bullshitbench_v2",
    task_id: str = "task_001",
    routing_regret: float | None = 50.0,
    oracle_policy_id: str | None = "single_pass",
    regret_status: str = "ok",
) -> RegretRecord:
    return RegretRecord(
        task_id=task_id,
        benchmark_id=benchmark_id,
        chosen_policy_id=chosen_policy_id,
        oracle_policy_id=oracle_policy_id,
        chosen_cost_dyn=200.0 if routing_regret is not None else None,
        cost_star=150.0,
        routing_regret=routing_regret,
        oracle_available=regret_status == "ok",
        regret_status=regret_status,
    )


# ---------------------------------------------------------------------------
# 1-3. Agrégation runs
# ---------------------------------------------------------------------------

class TestBuildPolicySummary:
    def test_aggregates_two_policies(self):
        runs = [
            make_run(policy_id="single_pass", task_id="t1"),
            make_run(policy_id="single_pass", task_id="t2"),
            make_run(policy_id="single_pass_verify", task_id="t3"),
        ]
        summaries = build_policy_summary_records(runs)
        assert len(summaries) == 2
        ids = [s.policy_id for s in summaries]
        assert "single_pass" in ids
        assert "single_pass_verify" in ids

    def test_quality_pass_rate(self):
        runs = [
            make_run(policy_id="single_pass", passed_quality=True, task_id="t1"),
            make_run(policy_id="single_pass", passed_quality=True, task_id="t2"),
            make_run(policy_id="single_pass", passed_quality=False, quality_score=1.0, task_id="t3"),
        ]
        summaries = build_policy_summary_records(runs)
        sp = next(s for s in summaries if s.policy_id == "single_pass")
        assert sp.num_runs == 3
        assert sp.num_quality_passed == 2
        assert sp.quality_pass_rate == pytest.approx(2 / 3)

    def test_mean_cost_dyn(self):
        runs = [
            make_run(policy_id="single_pass", cost_dyn=100.0, task_id="t1"),
            make_run(policy_id="single_pass", cost_dyn=200.0, task_id="t2"),
            make_run(policy_id="single_pass", cost_dyn=300.0, task_id="t3"),
        ]
        summaries = build_policy_summary_records(runs)
        sp = next(s for s in summaries if s.policy_id == "single_pass")
        assert sp.mean_cost_dyn == pytest.approx(200.0)
        assert sp.median_cost_dyn == pytest.approx(200.0)

    def test_null_cost_excluded(self):
        runs = [
            make_run(policy_id="single_pass", cost_dyn=None, task_id="t1"),
            make_run(policy_id="single_pass", cost_dyn=200.0, task_id="t2"),
        ]
        summaries = build_policy_summary_records(runs)
        sp = summaries[0]
        assert sp.mean_cost_dyn == pytest.approx(200.0)

    def test_benchmark_filter(self):
        runs = [
            make_run(policy_id="single_pass", benchmark_id="bench_a", task_id="t1"),
            make_run(policy_id="single_pass", benchmark_id="bench_b", task_id="t2"),
        ]
        summaries = build_policy_summary_records(runs, benchmark_id="bench_a")
        assert len(summaries) == 1
        assert summaries[0].num_runs == 1

    def test_sorted_by_policy_id(self):
        runs = [
            make_run(policy_id="z_policy", task_id="t1"),
            make_run(policy_id="a_policy", task_id="t2"),
        ]
        summaries = build_policy_summary_records(runs)
        assert summaries[0].policy_id == "a_policy"
        assert summaries[1].policy_id == "z_policy"


# ---------------------------------------------------------------------------
# 4-5. Fusion regrets
# ---------------------------------------------------------------------------

class TestRegretFusion:
    def test_merges_regrets_by_policy(self):
        runs = [
            make_run(policy_id="single_pass", task_id="t1"),
            make_run(policy_id="single_pass", task_id="t2"),
        ]
        regrets = [
            make_regret(chosen_policy_id="single_pass", task_id="t1", routing_regret=40.0),
            make_regret(chosen_policy_id="single_pass", task_id="t2", routing_regret=60.0),
        ]
        summaries = build_policy_summary_records(runs, regrets)
        sp = summaries[0]
        assert sp.mean_routing_regret == pytest.approx(50.0)

    def test_none_regret_if_no_computable(self):
        runs = [make_run(policy_id="single_pass", task_id="t1")]
        regrets = [
            make_regret(
                chosen_policy_id="single_pass", task_id="t1",
                routing_regret=None, regret_status="no_oracle",
            )
        ]
        summaries = build_policy_summary_records(runs, regrets)
        assert summaries[0].mean_routing_regret is None

    def test_oracle_match_rate(self):
        runs = [
            make_run(policy_id="single_pass", task_id="t1"),
            make_run(policy_id="single_pass", task_id="t2"),
        ]
        regrets = [
            make_regret(
                chosen_policy_id="single_pass", task_id="t1",
                routing_regret=0.0, oracle_policy_id="single_pass",
            ),
            make_regret(
                chosen_policy_id="single_pass", task_id="t2",
                routing_regret=50.0, oracle_policy_id="other_policy",
            ),
        ]
        summaries = build_policy_summary_records(runs, regrets)
        assert summaries[0].oracle_match_rate == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# 6-8. Recommandation
# ---------------------------------------------------------------------------

class TestRecommendation:
    def test_highest_pass_rate_wins(self):
        summaries = [
            PolicySummaryRecord(
                benchmark_id="b", policy_id="single_pass",
                quality_pass_rate=0.6, mean_routing_regret=30.0, mean_cost_dyn=200.0,
            ),
            PolicySummaryRecord(
                benchmark_id="b", policy_id="single_pass_verify",
                quality_pass_rate=0.8, mean_routing_regret=20.0, mean_cost_dyn=300.0,
            ),
        ]
        summary = summarize_sprint_outcome(summaries)
        assert summary["recommended_policy_id"] == "single_pass_verify"

    def test_regret_breaks_quality_tie(self):
        summaries = [
            PolicySummaryRecord(
                benchmark_id="b", policy_id="policy_a",
                quality_pass_rate=0.8, mean_routing_regret=40.0, mean_cost_dyn=200.0,
            ),
            PolicySummaryRecord(
                benchmark_id="b", policy_id="policy_b",
                quality_pass_rate=0.8, mean_routing_regret=20.0, mean_cost_dyn=300.0,
            ),
        ]
        summary = summarize_sprint_outcome(summaries)
        assert summary["recommended_policy_id"] == "policy_b"

    def test_cost_breaks_quality_and_regret_tie(self):
        summaries = [
            PolicySummaryRecord(
                benchmark_id="b", policy_id="policy_a",
                quality_pass_rate=0.8, mean_routing_regret=20.0, mean_cost_dyn=300.0,
            ),
            PolicySummaryRecord(
                benchmark_id="b", policy_id="policy_b",
                quality_pass_rate=0.8, mean_routing_regret=20.0, mean_cost_dyn=200.0,
            ),
        ]
        summary = summarize_sprint_outcome(summaries)
        assert summary["recommended_policy_id"] == "policy_b"

    def test_lexicographic_final_tie_break(self):
        summaries = [
            PolicySummaryRecord(
                benchmark_id="b", policy_id="z_policy",
                quality_pass_rate=0.8, mean_routing_regret=20.0, mean_cost_dyn=200.0,
            ),
            PolicySummaryRecord(
                benchmark_id="b", policy_id="a_policy",
                quality_pass_rate=0.8, mean_routing_regret=20.0, mean_cost_dyn=200.0,
            ),
        ]
        summary = summarize_sprint_outcome(summaries)
        assert summary["recommended_policy_id"] == "a_policy"

    def test_summary_fields_present(self):
        summaries = [
            PolicySummaryRecord(
                benchmark_id="bullshitbench_v2", policy_id="single_pass",
                quality_pass_rate=0.7, mean_cost_dyn=200.0,
            ),
        ]
        summary = summarize_sprint_outcome(summaries)
        for key in [
            "benchmark_id", "num_policies", "num_runs_total",
            "recommended_policy_id", "recommendation_reason",
            "best_quality_policy_id", "lowest_cost_policy_id",
        ]:
            assert key in summary


# ---------------------------------------------------------------------------
# 9. Rapport Markdown
# ---------------------------------------------------------------------------

class TestMarkdownReport:
    def _make_summaries(self):
        return [
            PolicySummaryRecord(
                benchmark_id="bullshitbench_v2", policy_id="single_pass",
                num_runs=10, quality_pass_rate=0.6,
                mean_cost_dyn=200.0, mean_routing_regret=30.0,
            ),
            PolicySummaryRecord(
                benchmark_id="bullshitbench_v2", policy_id="single_pass_verify",
                num_runs=10, quality_pass_rate=0.8,
                mean_cost_dyn=300.0, mean_routing_regret=20.0,
            ),
        ]

    def test_contains_recommended_policy(self):
        summaries = self._make_summaries()
        sprint = summarize_sprint_outcome(summaries)
        md = render_markdown_report(
            summaries, sprint, benchmark_id="bullshitbench_v2"
        )
        assert sprint["recommended_policy_id"] in md

    def test_contains_table(self):
        summaries = self._make_summaries()
        sprint = summarize_sprint_outcome(summaries)
        md = render_markdown_report(
            summaries, sprint, benchmark_id="bullshitbench_v2"
        )
        assert "| policy_id |" in md
        assert "single_pass" in md

    def test_contains_benchmark_id(self):
        summaries = self._make_summaries()
        sprint = summarize_sprint_outcome(summaries)
        md = render_markdown_report(
            summaries, sprint, benchmark_id="bullshitbench_v2"
        )
        assert "bullshitbench_v2" in md

    def test_contains_recommendation_section(self):
        summaries = self._make_summaries()
        sprint = summarize_sprint_outcome(summaries)
        md = render_markdown_report(
            summaries, sprint, benchmark_id="bullshitbench_v2"
        )
        assert "## Recommendation" in md

    def test_schema_version_constant(self):
        assert REPORTING_SCHEMA_VERSION == "reporting.v1"


# ---------------------------------------------------------------------------
# 10. CSV export
# ---------------------------------------------------------------------------

class TestCsvExport:
    def test_writes_valid_csv(self, tmp_path):
        summaries = [
            PolicySummaryRecord(
                benchmark_id="bullshitbench_v2",
                policy_id="single_pass",
                num_runs=5,
                quality_pass_rate=0.6,
                mean_cost_dyn=200.0,
            )
        ]
        path = tmp_path / "summary.csv"
        write_policy_summary_csv(path, summaries)

        with path.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["policy_id"] == "single_pass"
        assert rows[0]["num_runs"] == "5"

    def test_csv_has_all_fields(self, tmp_path):
        summaries = [
            PolicySummaryRecord(
                benchmark_id="b", policy_id="single_pass",
            )
        ]
        path = tmp_path / "summary.csv"
        write_policy_summary_csv(path, summaries)

        with path.open() as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

        for expected in ["policy_id", "quality_pass_rate", "mean_cost_dyn", "mean_routing_regret"]:
            assert expected in fieldnames

    def test_creates_parent_dirs(self, tmp_path):
        summaries = [PolicySummaryRecord(benchmark_id="b", policy_id="p")]
        path = tmp_path / "nested" / "dir" / "summary.csv"
        write_policy_summary_csv(path, summaries)
        assert path.exists()
