"""
tests/test_bullshitbench.py
===========================
Tests unitaires pour l'adaptateur BullshitBench v2 — Ticket 4 EGO Metrology.

Couvre tous les critères d'acceptation :
1.  charge un fixture tasks valide
2.  refuse un task sans prompt
3.  construit des task_id stables
4.  benchmark_id vaut bien bullshitbench_v2
5.  map_bullshitbench_score(0) → (0.0, 2.0, False)
6.  map_bullshitbench_score(1) → (1.0, 2.0, False)
7.  map_bullshitbench_score(2) → (2.0, 2.0, True)
8.  map_bullshitbench_score(None) → (None, None, None)
9.  crée un RunRecord depuis un BenchmarkTask
10. merge un BenchmarkJudgment cohérent dans un record
11. refuse un merge avec task_id différent
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from ego_metrology.benchmarks.bullshitbench import (
    BENCHMARK_ID,
    QUALITY_THRESHOLD,
    BenchmarkJudgment,
    BenchmarkTask,
    load_bullshitbench_judgments,
    load_bullshitbench_tasks,
    make_run_record_from_bullshitbench_task,
    map_bullshitbench_score,
    merge_bullshitbench_judgment_into_run,
)

FIXTURES = Path(__file__).parent / "fixtures"
TASKS_PATH = FIXTURES / "bullshitbench_sample_tasks.json"
JUDGMENTS_PATH = FIXTURES / "bullshitbench_sample_judgments.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RUN_KWARGS = dict(
    model_name="qwen2.5-14b",
    policy_id="single_pass",
    backend_name="local_vllm",
    manifest_hash="sha256:abc123",
    calibration_status="experimental",
    runner_version="ego-metrology/0.3.0-dev",
)


# ---------------------------------------------------------------------------
# 1. Chargement fixture tasks
# ---------------------------------------------------------------------------

class TestLoadTasks:
    def test_loads_all_items(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        assert len(tasks) == 5

    def test_all_are_benchmark_tasks(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        assert all(isinstance(t, BenchmarkTask) for t in tasks)

    def test_prompts_are_non_empty(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        assert all(len(t.prompt) > 0 for t in tasks)

    def test_domains_are_preserved(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        domains = [t.domain for t in tasks]
        assert "software" in domains
        assert "medical" in domains


# ---------------------------------------------------------------------------
# 2. Refus task sans prompt
# ---------------------------------------------------------------------------

class TestTaskValidation:
    def test_empty_prompt_raises(self):
        with pytest.raises(ValidationError):
            BenchmarkTask(
                task_id="bullshitbench_v2_test_0001",
                prompt="",
            )

    def test_missing_prompt_raises(self):
        with pytest.raises(ValidationError):
            BenchmarkTask(task_id="bullshitbench_v2_test_0001")

    def test_wrong_benchmark_id_raises(self):
        with pytest.raises(ValidationError, match="benchmark_id"):
            BenchmarkTask(
                task_id="other_bench_test_0001",
                benchmark_id="other_bench",
                prompt="Some prompt.",
            )


# ---------------------------------------------------------------------------
# 3. task_id stables
# ---------------------------------------------------------------------------

class TestTaskIds:
    def test_task_ids_are_stable(self):
        tasks1 = load_bullshitbench_tasks(TASKS_PATH)
        tasks2 = load_bullshitbench_tasks(TASKS_PATH)
        assert [t.task_id for t in tasks1] == [t.task_id for t in tasks2]

    def test_task_ids_are_unique(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        ids = [t.task_id for t in tasks]
        assert len(ids) == len(set(ids))

    def test_task_id_format(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        for task in tasks:
            assert task.task_id.startswith(BENCHMARK_ID)

    def test_task_id_includes_domain(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        software_task = next(t for t in tasks if t.domain == "software")
        assert "software" in software_task.task_id


# ---------------------------------------------------------------------------
# 4. benchmark_id canonique
# ---------------------------------------------------------------------------

class TestBenchmarkId:
    def test_all_tasks_have_correct_benchmark_id(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        assert all(t.benchmark_id == BENCHMARK_ID for t in tasks)

    def test_benchmark_id_constant(self):
        assert BENCHMARK_ID == "bullshitbench_v2"


# ---------------------------------------------------------------------------
# 5-8. map_bullshitbench_score
# ---------------------------------------------------------------------------

class TestMapScore:
    def test_score_0(self):
        assert map_bullshitbench_score(0) == (0.0, 2.0, False)

    def test_score_1(self):
        assert map_bullshitbench_score(1) == (1.0, 2.0, False)

    def test_score_2(self):
        assert map_bullshitbench_score(2) == (2.0, 2.0, True)

    def test_score_none(self):
        assert map_bullshitbench_score(None) == (None, None, None)

    def test_score_float_2(self):
        assert map_bullshitbench_score(2.0) == (2.0, 2.0, True)

    def test_invalid_score_raises(self):
        with pytest.raises(ValueError, match="invalide"):
            map_bullshitbench_score(3)

    def test_threshold_is_2(self):
        assert QUALITY_THRESHOLD == 2.0


# ---------------------------------------------------------------------------
# 9. RunRecord depuis BenchmarkTask
# ---------------------------------------------------------------------------

class TestMakeRunRecord:
    def test_creates_valid_run_record(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        record = make_run_record_from_bullshitbench_task(tasks[0], **RUN_KWARGS)
        assert record.task_id == tasks[0].task_id
        assert record.benchmark_id == BENCHMARK_ID

    def test_quality_fields_are_null(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        record = make_run_record_from_bullshitbench_task(tasks[0], **RUN_KWARGS)
        assert record.quality_score is None
        assert record.quality_threshold is None
        assert record.passed_quality is None

    def test_cost_fields_are_null(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        record = make_run_record_from_bullshitbench_task(tasks[0], **RUN_KWARGS)
        assert record.total_tokens is None
        assert record.latency_ms is None
        assert record.cost_dyn is None

    def test_meta_contains_domain(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        record = make_run_record_from_bullshitbench_task(tasks[0], **RUN_KWARGS)
        assert "domain" in record.meta

    def test_run_id_is_non_empty(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        record = make_run_record_from_bullshitbench_task(tasks[0], **RUN_KWARGS)
        assert len(record.run_id) > 0


# ---------------------------------------------------------------------------
# 10. Merge judgment dans RunRecord
# ---------------------------------------------------------------------------

class TestMergeJudgment:
    def _make_task_and_record(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        task = tasks[0]
        record = make_run_record_from_bullshitbench_task(task, **RUN_KWARGS)
        return task, record

    def test_merge_enriches_quality(self):
        task, record = self._make_task_and_record()
        judgment = BenchmarkJudgment(
            task_id=task.task_id,
            quality_score=2.0,
            quality_threshold=2.0,
            passed_quality=True,
            raw_label="clear_pushback",
            judge_source="fixture",
        )
        enriched = merge_bullshitbench_judgment_into_run(record, judgment)
        assert enriched.quality_score == 2.0
        assert enriched.passed_quality is True

    def test_merge_does_not_mutate_original(self):
        task, record = self._make_task_and_record()
        judgment = BenchmarkJudgment(
            task_id=task.task_id,
            quality_score=2.0,
            quality_threshold=2.0,
            passed_quality=True,
        )
        merge_bullshitbench_judgment_into_run(record, judgment)
        assert record.quality_score is None

    def test_overwrite_false_preserves_existing(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        task = tasks[0]
        record = make_run_record_from_bullshitbench_task(task, **RUN_KWARGS)
        record = record.model_copy(update={
            "quality_score": 1.0,
            "quality_threshold": 2.0,
            "passed_quality": False,
        })
        judgment = BenchmarkJudgment(
            task_id=task.task_id,
            quality_score=2.0,
            quality_threshold=2.0,
            passed_quality=True,
        )
        enriched = merge_bullshitbench_judgment_into_run(record, judgment, overwrite=False)
        assert enriched.quality_score == 1.0

    def test_load_judgments_fixture(self):
        judgments = load_bullshitbench_judgments(JUDGMENTS_PATH)
        assert len(judgments) == 3
        assert judgments[0].quality_score == 2.0
        assert judgments[0].passed_quality is True

    def test_task_meta_survives_to_run_record(self):
        """Les champs extra de task.meta doivent survivre dans le RunRecord."""
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        task = tasks[0]
        record = make_run_record_from_bullshitbench_task(task, **RUN_KWARGS)
        assert "domain" in record.meta
        assert "technique" in record.meta
        assert "source_ref" in record.meta

    def test_judgment_meta_survives_to_run_record(self):
        """Les champs extra de judgment.meta doivent survivre après merge."""
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        task = tasks[0]
        record = make_run_record_from_bullshitbench_task(task, **RUN_KWARGS)
        judgment = BenchmarkJudgment(
            task_id=task.task_id,
            quality_score=2.0,
            quality_threshold=2.0,
            passed_quality=True,
            raw_label="clear_pushback",
            judge_source="fixture",
            meta={"extra_field": "extra_value"},
        )
        enriched = merge_bullshitbench_judgment_into_run(record, judgment)
        assert enriched.meta.get("extra_field") == "extra_value"
        assert enriched.meta.get("raw_label") == "clear_pushback"


# ---------------------------------------------------------------------------
# 11. Refus merge task_id différent
# ---------------------------------------------------------------------------

class TestMergeMismatch:
    def test_mismatched_task_id_raises(self):
        tasks = load_bullshitbench_tasks(TASKS_PATH)
        record = make_run_record_from_bullshitbench_task(tasks[0], **RUN_KWARGS)
        judgment = BenchmarkJudgment(
            task_id="bullshitbench_v2_other_9999",
            quality_score=2.0,
            quality_threshold=2.0,
            passed_quality=True,
        )
        with pytest.raises(ValueError, match="task_id incompatible"):
            merge_bullshitbench_judgment_into_run(record, judgment)
