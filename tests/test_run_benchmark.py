"""
tests/test_run_benchmark.py
===========================
Tests unitaires pour le runner canonique — Ticket 5 EGO Metrology.

Couvre tous les critères d'acceptation :
1.  dry run single_pass produit un RunRecord valide
2.  backend fake single_pass remplit tokens/latence/cost
3.  output_jsonl_path écrit bien une ligne append-only
4.  quality_score reste None sans jugement
5.  cost_dyn est calculé quand données présentes
6.  erreur si dry_run=False et backend absent
7.  erreur si policy_id inconnu
8.  single_pass_verify en dry run passe
9.  single_pass_verify en exécution réelle lève NotImplementedError
10. merge propre de backend_meta dans meta
"""

from pathlib import Path

import pytest

from ego_metrology.backends.base import FakeBackend
from ego_metrology.benchmarks.bullshitbench import load_bullshitbench_tasks
from ego_metrology.logging_schema import load_run_records_jsonl
from ego_metrology.policies import load_policy_registry
from ego_metrology.runners.run_benchmark import run_task_id_with_policy, run_task_with_policy

FIXTURES = Path(__file__).parent / "fixtures"
TASKS_PATH = FIXTURES / "bullshitbench_sample_tasks.json"
REGISTRY_PATH = Path(__file__).parent.parent / "ego_metrology" / "policy_registry.json"

BASE_KWARGS = dict(
    model_name="qwen2.5-14b",
    backend_name="fake_backend",
    manifest_hash="sha256:abc123",
    calibration_status="experimental",
    runner_version="ego-metrology/0.3.0-dev",
)


def get_tasks():
    return load_bullshitbench_tasks(TASKS_PATH)


def get_registry():
    return load_policy_registry(REGISTRY_PATH)


def first_task():
    return get_tasks()[0]


# ---------------------------------------------------------------------------
# 1. Dry run single_pass → RunRecord valide
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_single_pass_valid(self):
        record = run_task_with_policy(
            task=first_task(),
            policy_id="single_pass",
            registry=get_registry(),
            dry_run=True,
            **BASE_KWARGS,
        )
        assert record.task_id == first_task().task_id
        assert record.policy_id == "single_pass"
        assert record.run_id != ""

    def test_dry_run_tokens_are_null(self):
        record = run_task_with_policy(
            task=first_task(),
            policy_id="single_pass",
            registry=get_registry(),
            dry_run=True,
            **BASE_KWARGS,
        )
        assert record.prompt_tokens is None
        assert record.completion_tokens is None
        assert record.total_tokens is None
        assert record.latency_ms is None
        assert record.latency_total_ms is None
        assert record.provider_name is None
        assert record.metrics_source is None

    def test_dry_run_cost_dyn_is_null(self):
        record = run_task_with_policy(
            task=first_task(),
            policy_id="single_pass",
            registry=get_registry(),
            dry_run=True,
            **BASE_KWARGS,
        )
        assert record.cost_dyn is None

    def test_dry_run_meta_contains_dry_run_flag(self):
        record = run_task_with_policy(
            task=first_task(),
            policy_id="single_pass",
            registry=get_registry(),
            dry_run=True,
            **BASE_KWARGS,
        )
        assert record.meta.get("dry_run") is True


# ---------------------------------------------------------------------------
# 2. Backend fake single_pass → tokens/latence/cost remplis
# ---------------------------------------------------------------------------

class TestFakeBackend:
    def test_tokens_filled(self):
        record = run_task_with_policy(
            task=first_task(),
            policy_id="single_pass",
            registry=get_registry(),
            backend=FakeBackend(),
            dry_run=False,
            **BASE_KWARGS,
        )
        assert record.prompt_tokens == 120
        assert record.completion_tokens == 48
        assert record.total_tokens == 168

    def test_latency_filled(self):
        record = run_task_with_policy(
            task=first_task(),
            policy_id="single_pass",
            registry=get_registry(),
            backend=FakeBackend(),
            dry_run=False,
            **BASE_KWARGS,
        )
        assert record.latency_ms == pytest.approx(250.0)

    def test_latency_total_filled(self):
        record = run_task_with_policy(
            task=first_task(),
            policy_id="single_pass",
            registry=get_registry(),
            backend=FakeBackend(),
            dry_run=False,
            **BASE_KWARGS,
        )
        assert record.latency_total_ms == pytest.approx(250.0)

    def test_runtime_v2_fields_propagated(self):
        record = run_task_with_policy(
            task=first_task(),
            policy_id="single_pass",
            registry=get_registry(),
            backend=FakeBackend(),
            dry_run=False,
            **BASE_KWARGS,
        )
        assert record.provider_name == "fake"
        assert record.metrics_source == "derived"

    def test_cost_dyn_calculated(self):
        record = run_task_with_policy(
            task=first_task(),
            policy_id="single_pass",
            registry=get_registry(),
            backend=FakeBackend(),
            dry_run=False,
            **BASE_KWARGS,
        )
        # cost_dyn = 168 + 0.001 * 250 = 168.25
        assert record.cost_dyn == pytest.approx(168.25)


# ---------------------------------------------------------------------------
# 3. JSONL append-only
# ---------------------------------------------------------------------------

class TestJsonlOutput:
    def test_writes_one_line(self, tmp_path):
        output = tmp_path / "runs.jsonl"
        run_task_with_policy(
            task=first_task(),
            policy_id="single_pass",
            registry=get_registry(),
            dry_run=True,
            output_jsonl_path=str(output),
            **BASE_KWARGS,
        )
        records = load_run_records_jsonl(str(output))
        assert len(records) == 1

    def test_appends_multiple_runs(self, tmp_path):
        output = tmp_path / "runs.jsonl"
        tasks = get_tasks()
        for task in tasks[:3]:
            run_task_with_policy(
                task=task,
                policy_id="single_pass",
                registry=get_registry(),
                dry_run=True,
                output_jsonl_path=str(output),
                **BASE_KWARGS,
            )
        records = load_run_records_jsonl(str(output))
        assert len(records) == 3

    def test_creates_parent_dirs(self, tmp_path):
        output = tmp_path / "nested" / "dir" / "runs.jsonl"
        run_task_with_policy(
            task=first_task(),
            policy_id="single_pass",
            registry=get_registry(),
            dry_run=True,
            output_jsonl_path=str(output),
            **BASE_KWARGS,
        )
        assert output.exists()


# ---------------------------------------------------------------------------
# 4. quality_score reste None sans jugement
# ---------------------------------------------------------------------------

class TestQualityNull:
    def test_quality_score_null(self):
        record = run_task_with_policy(
            task=first_task(),
            policy_id="single_pass",
            registry=get_registry(),
            dry_run=True,
            **BASE_KWARGS,
        )
        assert record.quality_score is None
        assert record.quality_threshold is None
        assert record.passed_quality is None


# ---------------------------------------------------------------------------
# 5. cost_dyn calculé quand données présentes — déjà couvert dans TestFakeBackend
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 6. Erreur si dry_run=False et backend absent
# ---------------------------------------------------------------------------

class TestBackendRequired:
    def test_no_backend_real_run_raises(self):
        with pytest.raises(ValueError, match="backend"):
            run_task_with_policy(
                task=first_task(),
                policy_id="single_pass",
                registry=get_registry(),
                backend=None,
                dry_run=False,
                **BASE_KWARGS,
            )


# ---------------------------------------------------------------------------
# 7. Erreur si policy_id inconnu
# ---------------------------------------------------------------------------

class TestUnknownPolicy:
    def test_unknown_policy_raises(self):
        with pytest.raises(KeyError, match="absent du registry"):
            run_task_with_policy(
                task=first_task(),
                policy_id="nonexistent_policy",
                registry=get_registry(),
                dry_run=True,
                **BASE_KWARGS,
            )


# ---------------------------------------------------------------------------
# 8. single_pass_verify en dry run → OK
# ---------------------------------------------------------------------------

class TestDryRunOnlyPolicies:
    def test_single_pass_verify_dry_run_ok(self):
        record = run_task_with_policy(
            task=first_task(),
            policy_id="single_pass_verify",
            registry=get_registry(),
            dry_run=True,
            **BASE_KWARGS,
        )
        assert record.policy_id == "single_pass_verify"

    def test_cascade_dry_run_ok(self):
        record = run_task_with_policy(
            task=first_task(),
            policy_id="cascade_small_to_large",
            registry=get_registry(),
            dry_run=True,
            **BASE_KWARGS,
        )
        assert record.policy_id == "cascade_small_to_large"


# ---------------------------------------------------------------------------
# 9. single_pass_verify en exécution réelle → NotImplementedError
# ---------------------------------------------------------------------------

class TestNotImplementedPolicies:
    def test_single_pass_verify_real_raises(self):
        with pytest.raises(NotImplementedError, match="single_pass_verify"):
            run_task_with_policy(
                task=first_task(),
                policy_id="single_pass_verify",
                registry=get_registry(),
                backend=FakeBackend(),
                dry_run=False,
                **BASE_KWARGS,
            )

    def test_cascade_real_raises(self):
        with pytest.raises(NotImplementedError, match="cascade_small_to_large"):
            run_task_with_policy(
                task=first_task(),
                policy_id="cascade_small_to_large",
                registry=get_registry(),
                backend=FakeBackend(),
                dry_run=False,
                **BASE_KWARGS,
            )


# ---------------------------------------------------------------------------
# 10. backend_meta dans meta
# ---------------------------------------------------------------------------

class TestBackendMeta:
    def test_backend_meta_in_record_meta(self):
        record = run_task_with_policy(
            task=first_task(),
            policy_id="single_pass",
            registry=get_registry(),
            backend=FakeBackend(),
            dry_run=False,
            **BASE_KWARGS,
        )
        assert "backend_meta" in record.meta
        assert record.meta["backend_meta"]["backend"] == "fake"

    def test_response_text_in_meta(self):
        record = run_task_with_policy(
            task=first_task(),
            policy_id="single_pass",
            registry=get_registry(),
            backend=FakeBackend(),
            dry_run=False,
            **BASE_KWARGS,
        )
        assert "response_text" in record.meta
        assert len(record.meta["response_text"]) > 0


# ---------------------------------------------------------------------------
# run_task_id_with_policy
# ---------------------------------------------------------------------------

class TestRunTaskIdWithPolicy:
    def test_resolves_task_by_id(self):
        tasks = get_tasks()
        target = tasks[0]
        record = run_task_id_with_policy(
            task_id=target.task_id,
            tasks=tasks,
            registry=get_registry(),
            policy_id="single_pass",
            dry_run=True,
            **BASE_KWARGS,
        )
        assert record.task_id == target.task_id

    def test_unknown_task_id_raises(self):
        with pytest.raises(KeyError, match="absent de la liste"):
            run_task_id_with_policy(
                task_id="bullshitbench_v2_unknown_9999",
                tasks=get_tasks(),
                registry=get_registry(),
                policy_id="single_pass",
                dry_run=True,
                **BASE_KWARGS,
            )
