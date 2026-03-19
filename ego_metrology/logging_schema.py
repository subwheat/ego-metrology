"""
ego_metrology.logging_schema
============================
RunRecord — unité atomique de mesure d'un run EGO Metrology.
Schema version : runrecord.v1

1 ligne JSONL = 1 exécution de (task × policy × model).
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "runrecord.v1"

CalibrationStatus = Literal["experimental", "candidate", "frozen"]


# ---------------------------------------------------------------------------
# RunRecord
# ---------------------------------------------------------------------------

class RunRecord(BaseModel):
    """Enregistrement canonique d'un run EGO Metrology."""

    # --- A. Identité ---
    run_id: str = Field(..., min_length=1)
    timestamp_utc: str = Field(..., description="ISO-8601 UTC, ex: 2026-03-19T16:42:31Z")
    task_id: str = Field(..., min_length=1)
    benchmark_id: str = Field(..., min_length=1)
    model_name: str = Field(..., min_length=1)
    policy_id: str = Field(..., min_length=1)

    # --- B. Qualité ---
    quality_score: Optional[float] = None
    quality_threshold: Optional[float] = None
    passed_quality: Optional[bool] = None

    # --- C. Usage / coût ---
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[float] = None
    cost_dyn: Optional[float] = None  # calcul réel = Ticket 3

    # --- D. Exécution / provenance ---
    backend_name: str = Field(..., min_length=1)
    manifest_hash: str = Field(..., min_length=1)
    calibration_status: CalibrationStatus

    # --- E. Reproductibilité ---
    seed: Optional[int] = None
    runner_version: str = Field(..., min_length=1)
    schema_version: str = Field(default=SCHEMA_VERSION)

    # --- F. Extension sûre ---
    meta: dict[str, Any] = Field(default_factory=dict)

    # ------------------------------------------------------------------
    # Validations logiques croisées (R2, R3, schema_version)
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _check_schema_version(self) -> "RunRecord":
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"schema_version doit être '{SCHEMA_VERSION}', reçu '{self.schema_version}'"
            )
        return self

    @model_validator(mode="after")
    def _check_total_tokens(self) -> "RunRecord":
        """R2 — total_tokens doit égaler prompt + completion si les deux sont présents."""
        p, c, t = self.prompt_tokens, self.completion_tokens, self.total_tokens
        if p is not None and c is not None:
            expected = p + c
            if t is not None and t != expected:
                raise ValueError(
                    f"total_tokens incohérent : {p} + {c} = {expected}, reçu {t}"
                )
        return self

    @model_validator(mode="after")
    def _check_passed_quality(self) -> "RunRecord":
        """R3 — passed_quality doit être cohérent avec score et threshold."""
        s, th, pq = self.quality_score, self.quality_threshold, self.passed_quality
        if s is not None and th is not None and pq is not None:
            expected = s >= th
            if pq != expected:
                raise ValueError(
                    f"passed_quality incohérent : score={s}, threshold={th} "
                    f"=> attendu {expected}, reçu {pq}"
                )
        return self


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------

def make_run_record(**kwargs: Any) -> RunRecord:
    """
    Crée un RunRecord validé.

    Si prompt_tokens et completion_tokens sont fournis sans total_tokens,
    total_tokens est calculé automatiquement.

    Si quality_score et quality_threshold sont fournis sans passed_quality,
    passed_quality est déduit automatiquement.
    """
    # Auto-calcul total_tokens (R2)
    p = kwargs.get("prompt_tokens")
    c = kwargs.get("completion_tokens")
    if p is not None and c is not None and kwargs.get("total_tokens") is None:
        kwargs["total_tokens"] = p + c

    # Auto-calcul passed_quality (R3)
    s = kwargs.get("quality_score")
    th = kwargs.get("quality_threshold")
    if s is not None and th is not None and kwargs.get("passed_quality") is None:
        kwargs["passed_quality"] = s >= th

    return RunRecord(**kwargs)


def append_run_record_jsonl(path: str, record: RunRecord) -> None:
    """Écrit un RunRecord en mode append-only dans un fichier JSONL."""
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(record.model_dump_json() + "\n")


def load_run_records_jsonl(path: str) -> list[RunRecord]:
    """Charge tous les RunRecords depuis un fichier JSONL."""
    records: list[RunRecord] = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(RunRecord.model_validate_json(line))
            except Exception as exc:
                raise ValueError(f"Ligne {lineno} invalide dans {path}: {exc}") from exc
    return records
