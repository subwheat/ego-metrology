"""
tests/test_logging_schema.py
============================
Tests unitaires pour RunRecord — Ticket 1 EGO Metrology.

Couvre tous les critères d'acceptation :
1. run valide créable
2. écriture JSONL append-only
3. refus record invalide (champs obligatoires manquants ou vides)
4. refus total_tokens incohérent (R2)
5. refus passed_quality incohérent (R3)
6. refus schema_version incorrecte
7. auto-calcul total_tokens et passed_quality dans make_run_record
8. chargement JSONL multi-lignes
"""

import json
import os

import pytest
from pydantic import ValidationError

from ego_metrology.logging_schema import (
    RunRecord,
    append_run_record_jsonl,
    load_run_records_jsonl,
    make_run_record,
    SCHEMA_VERSION,
)


# ---------------------------------------------------------------------------
# Fixture : record valide minimal
# ---------------------------------------------------------------------------

VALID_KWARGS = dict(
    run_id="01HRYV8ST0FK8Q6M7N0K6Y4F3A",
    timestamp_utc="2026-03-19T16:42:31Z",
    task_id="bullshitbench_v2_software_0042",
    benchmark_id="bullshitbench_v2",
    model_name="mistralai/Mistral-7B-Instruct-v0.2",
    policy_id="single_pass",
    backend_name="local_vllm",
    manifest_hash="sha256:5c8c8db1d8d7b8c2d6d5d3a9161d2c8f",
    calibration_status="experimental",
    runner_version="ego-metrology/0.3.0-dev",
    schema_version=SCHEMA_VERSION,
)


# ---------------------------------------------------------------------------
# 1. Run valide créable
# ---------------------------------------------------------------------------

class TestValidRecord:
    def test_minimal_valid(self):
        r = RunRecord(**VALID_KWARGS)
        assert r.run_id == "01HRYV8ST0FK8Q6M7N0K6Y4F3A"
        assert r.schema_version == SCHEMA_VERSION

    def test_all_nullable_fields_can_be_none(self):
        r = RunRecord(**VALID_KWARGS)
        assert r.quality_score is None
        assert r.quality_threshold is None
        assert r.passed_quality is None
        assert r.prompt_tokens is None
        assert r.completion_tokens is None
        assert r.total_tokens is None
        assert r.cost_dyn is None
        assert r.seed is None

    def test_meta_defaults_to_empty_dict(self):
        r = RunRecord(**VALID_KWARGS)
        assert r.meta == {}

    def test_full_record_with_tokens_and_quality(self):
        r = RunRecord(
            **VALID_KWARGS,
            quality_score=2.5,
            quality_threshold=2.0,
            passed_quality=True,
            prompt_tokens=814,
            completion_tokens=121,
            total_tokens=935,
            latency_ms=1842.6,
            meta={"judge_source": "bullshitbench_import"},
        )
        assert r.passed_quality is True
        assert r.total_tokens == 935


# ---------------------------------------------------------------------------
# 2. JSONL append-only
# ---------------------------------------------------------------------------

class TestJsonlIO:
    def test_append_and_reload(self, tmp_path):
        path = str(tmp_path / "runs.jsonl")
        r = RunRecord(**VALID_KWARGS)
        append_run_record_jsonl(path, r)

        records = load_run_records_jsonl(path)
        assert len(records) == 1
        assert records[0].run_id == r.run_id

    def test_append_multiple(self, tmp_path):
        path = str(tmp_path / "runs.jsonl")
        for i in range(5):
            r = RunRecord(**{**VALID_KWARGS, "run_id": f"RUN_{i:04d}", "task_id": f"task_{i}"})
            append_run_record_jsonl(path, r)

        records = load_run_records_jsonl(path)
        assert len(records) == 5
        assert records[2].run_id == "RUN_0002"

    def test_output_is_valid_json_lines(self, tmp_path):
        path = str(tmp_path / "runs.jsonl")
        r = RunRecord(**VALID_KWARGS)
        append_run_record_jsonl(path, r)

        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["run_id"] == r.run_id

    def test_load_raises_on_corrupt_line(self, tmp_path):
        path = str(tmp_path / "runs.jsonl")
        with open(path, "w") as f:
            f.write('{"not": "a valid RunRecord"}\n')
        with pytest.raises(ValueError, match="Ligne 1 invalide"):
            load_run_records_jsonl(path)


# ---------------------------------------------------------------------------
# 3. Refus champs obligatoires manquants
# ---------------------------------------------------------------------------

class TestMissingRequiredFields:
    @pytest.mark.parametrize("field", [
        "run_id", "timestamp_utc", "task_id", "benchmark_id",
        "model_name", "policy_id", "backend_name", "manifest_hash",
        "calibration_status", "runner_version",
    ])
    def test_missing_field_raises(self, field):
        kwargs = {k: v for k, v in VALID_KWARGS.items() if k != field}
        with pytest.raises(ValidationError):
            RunRecord(**kwargs)

    def test_empty_run_id_raises(self):
        with pytest.raises(ValidationError):
            RunRecord(**{**VALID_KWARGS, "run_id": ""})

    def test_empty_task_id_raises(self):
        with pytest.raises(ValidationError):
            RunRecord(**{**VALID_KWARGS, "task_id": ""})

    def test_empty_model_name_raises(self):
        with pytest.raises(ValidationError):
            RunRecord(**{**VALID_KWARGS, "model_name": ""})

    def test_empty_policy_id_raises(self):
        with pytest.raises(ValidationError):
            RunRecord(**{**VALID_KWARGS, "policy_id": ""})

    def test_empty_backend_name_raises(self):
        with pytest.raises(ValidationError):
            RunRecord(**{**VALID_KWARGS, "backend_name": ""})

    def test_empty_manifest_hash_raises(self):
        with pytest.raises(ValidationError):
            RunRecord(**{**VALID_KWARGS, "manifest_hash": ""})

    def test_empty_runner_version_raises(self):
        with pytest.raises(ValidationError):
            RunRecord(**{**VALID_KWARGS, "runner_version": ""})


# ---------------------------------------------------------------------------
# 4. Règle R2 — total_tokens cohérence
# ---------------------------------------------------------------------------

class TestTotalTokensRule:
    def test_coherent_total_accepted(self):
        r = RunRecord(**VALID_KWARGS, prompt_tokens=800, completion_tokens=100, total_tokens=900)
        assert r.total_tokens == 900

    def test_incoherent_total_raises(self):
        with pytest.raises(ValidationError, match="total_tokens incohérent"):
            RunRecord(**VALID_KWARGS, prompt_tokens=800, completion_tokens=100, total_tokens=999)

    def test_total_none_with_both_parts_accepted(self):
        # total_tokens=None est acceptable (sera auto-calculé par make_run_record)
        r = RunRecord(**VALID_KWARGS, prompt_tokens=800, completion_tokens=100, total_tokens=None)
        assert r.total_tokens is None

    def test_partial_tokens_no_constraint(self):
        # Seulement prompt_tokens, pas de completion → pas de contrainte
        r = RunRecord(**VALID_KWARGS, prompt_tokens=800)
        assert r.prompt_tokens == 800
        assert r.total_tokens is None


# ---------------------------------------------------------------------------
# 5. Règle R3 — passed_quality cohérence
# ---------------------------------------------------------------------------

class TestPassedQualityRule:
    def test_passed_true_coherent(self):
        r = RunRecord(**VALID_KWARGS, quality_score=3.0, quality_threshold=2.0, passed_quality=True)
        assert r.passed_quality is True

    def test_passed_false_coherent(self):
        r = RunRecord(**VALID_KWARGS, quality_score=1.0, quality_threshold=2.0, passed_quality=False)
        assert r.passed_quality is False

    def test_passed_true_incoherent_raises(self):
        with pytest.raises(ValidationError, match="passed_quality incohérent"):
            RunRecord(**VALID_KWARGS, quality_score=1.0, quality_threshold=2.0, passed_quality=True)

    def test_passed_false_incoherent_raises(self):
        with pytest.raises(ValidationError, match="passed_quality incohérent"):
            RunRecord(**VALID_KWARGS, quality_score=3.0, quality_threshold=2.0, passed_quality=False)

    def test_passed_none_with_score_and_threshold_accepted(self):
        # null explicite = "pas encore calculé"
        r = RunRecord(**VALID_KWARGS, quality_score=3.0, quality_threshold=2.0, passed_quality=None)
        assert r.passed_quality is None

    def test_at_threshold_boundary_is_pass(self):
        r = RunRecord(**VALID_KWARGS, quality_score=2.0, quality_threshold=2.0, passed_quality=True)
        assert r.passed_quality is True


# ---------------------------------------------------------------------------
# 6. schema_version
# ---------------------------------------------------------------------------

class TestSchemaVersion:
    def test_wrong_schema_version_raises(self):
        with pytest.raises(ValidationError, match="schema_version"):
            RunRecord(**{**VALID_KWARGS, "schema_version": "runrecord.v0"})

    def test_default_schema_version_correct(self):
        kwargs = {k: v for k, v in VALID_KWARGS.items() if k != "schema_version"}
        r = RunRecord(**kwargs)
        assert r.schema_version == SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 7. make_run_record — auto-calculs
# ---------------------------------------------------------------------------

class TestMakeRunRecord:
    def test_auto_total_tokens(self):
        r = make_run_record(**VALID_KWARGS, prompt_tokens=700, completion_tokens=150)
        assert r.total_tokens == 850

    def test_auto_passed_quality_true(self):
        r = make_run_record(**VALID_KWARGS, quality_score=3.0, quality_threshold=2.0)
        assert r.passed_quality is True

    def test_auto_passed_quality_false(self):
        r = make_run_record(**VALID_KWARGS, quality_score=1.5, quality_threshold=2.0)
        assert r.passed_quality is False

    def test_explicit_values_not_overridden(self):
        # Si total_tokens est déjà fourni et cohérent, make_run_record ne l'écrase pas
        r = make_run_record(**VALID_KWARGS, prompt_tokens=700, completion_tokens=150, total_tokens=850)
        assert r.total_tokens == 850

    def test_calibration_status_values(self):
        for status in ("experimental", "candidate", "frozen"):
            r = make_run_record(**{**VALID_KWARGS, "calibration_status": status})
            assert r.calibration_status == status

    def test_invalid_calibration_status_raises(self):
        with pytest.raises(ValidationError):
            make_run_record(**{**VALID_KWARGS, "calibration_status": "draft"})
