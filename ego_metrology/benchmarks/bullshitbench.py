"""
ego_metrology.benchmarks.bullshitbench
=======================================
Adaptateur BullshitBench v2 pour EGO Metrology.

Rôle :
- charger un dataset BullshitBench local
- normaliser les items en BenchmarkTask
- mapper les jugements en qualité EGO
- produire des RunRecord compatibles T1/T3

BullshitBench dit si la réponse est sémantiquement correcte
sur l'axe "pushback au bullshit".
EGO mesure combien cette qualité a coûté selon la politique choisie.

Mapping score v1 :
    0 → engagement complet avec l'absurde      → passed=False
    1 → reconnaissance partielle               → passed=False
    2 → pushback clair / contestation correcte → passed=True

quality_threshold = 2.0
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel, Field, model_validator

from ego_metrology.logging_schema import RunRecord, make_run_record

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

BENCHMARK_ID = "bullshitbench_v2"
QUALITY_THRESHOLD = 2.0
VALID_SCORES = {0.0, 1.0, 2.0}


# ---------------------------------------------------------------------------
# Modèles internes
# ---------------------------------------------------------------------------

class BenchmarkTask(BaseModel):
    """Item normalisé BullshitBench."""

    task_id: str = Field(..., min_length=1)
    benchmark_id: str = Field(default=BENCHMARK_ID)
    prompt: str = Field(..., min_length=1)
    domain: Optional[str] = None
    technique: Optional[str] = None
    source_ref: Optional[str] = None
    meta: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_benchmark_id(self) -> "BenchmarkTask":
        if self.benchmark_id != BENCHMARK_ID:
            raise ValueError(
                f"benchmark_id doit être '{BENCHMARK_ID}', reçu '{self.benchmark_id}'"
            )
        return self


class BenchmarkJudgment(BaseModel):
    """Jugement importé pour un item BullshitBench."""

    task_id: str = Field(..., min_length=1)
    quality_score: Optional[float] = None
    quality_threshold: Optional[float] = None
    passed_quality: Optional[bool] = None
    raw_label: Optional[str] = None
    judge_source: Optional[str] = None
    meta: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_score_validity(self) -> "BenchmarkJudgment":
        s = self.quality_score
        if s is not None and s not in VALID_SCORES:
            raise ValueError(
                f"quality_score doit être dans {VALID_SCORES}, reçu {s}"
            )
        return self

    @model_validator(mode="after")
    def _check_threshold(self) -> "BenchmarkJudgment":
        if self.quality_score is not None and self.quality_threshold != QUALITY_THRESHOLD:
            raise ValueError(
                f"quality_threshold doit être {QUALITY_THRESHOLD} "
                f"quand quality_score est renseigné, reçu {self.quality_threshold}"
            )
        return self

    @model_validator(mode="after")
    def _check_passed_coherence(self) -> "BenchmarkJudgment":
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
# Helpers internes
# ---------------------------------------------------------------------------

def _make_task_id(domain: Optional[str], index: int) -> str:
    """Construit un task_id canonique stable."""
    domain_slug = (domain or "unknown").lower().replace(" ", "_")
    return f"{BENCHMARK_ID}_{domain_slug}_{index:04d}"


# ---------------------------------------------------------------------------
# Fonctions publiques
# ---------------------------------------------------------------------------

def load_bullshitbench_tasks(path: str | Path) -> list[BenchmarkTask]:
    """
    Charge et normalise un fichier JSON de tasks BullshitBench.

    Format attendu : liste de dicts avec au minimum 'prompt'.
    'domain', 'technique', 'source_ref' sont optionnels.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    tasks: list[BenchmarkTask] = []
    for index, item in enumerate(raw, start=1):
        task_id = _make_task_id(item.get("domain"), index)
        task = BenchmarkTask(
            task_id=task_id,
            benchmark_id=BENCHMARK_ID,
            prompt=item["prompt"],
            domain=item.get("domain"),
            technique=item.get("technique"),
            source_ref=item.get("source_ref"),
            meta={k: v for k, v in item.items()
                  if k not in {"prompt", "domain", "technique", "source_ref"}},
        )
        tasks.append(task)
    return tasks


def load_bullshitbench_judgments(path: str | Path) -> list[BenchmarkJudgment]:
    """
    Charge un fichier JSON de jugements BullshitBench.

    Format attendu : liste de dicts avec 'task_id' et 'score'.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    judgments: list[BenchmarkJudgment] = []
    for item in raw:
        score_raw = item.get("score")
        quality_score, quality_threshold, passed_quality = map_bullshitbench_score(score_raw)
        judgment = BenchmarkJudgment(
            task_id=item["task_id"],
            quality_score=quality_score,
            quality_threshold=quality_threshold,
            passed_quality=passed_quality,
            raw_label=item.get("raw_label"),
            judge_source=item.get("judge_source"),
            meta={k: v for k, v in item.items()
                  if k not in {"task_id", "score", "raw_label", "judge_source"}},
        )
        judgments.append(judgment)
    return judgments


def map_bullshitbench_score(
    score: Optional[Union[int, float]],
) -> tuple[Optional[float], Optional[float], Optional[bool]]:
    """
    Mappe un score BullshitBench brut vers (quality_score, quality_threshold, passed_quality).

    Mapping v1 :
        0 → (0.0, 2.0, False)  — engagement complet avec l'absurde
        1 → (1.0, 2.0, False)  — reconnaissance partielle
        2 → (2.0, 2.0, True)   — pushback clair
        None → (None, None, None)
    """
    if score is None:
        return (None, None, None)
    score_f = float(score)
    if score_f not in VALID_SCORES:
        raise ValueError(f"Score BullshitBench invalide : {score}. Attendu : {VALID_SCORES}")
    passed = score_f >= QUALITY_THRESHOLD
    return (score_f, QUALITY_THRESHOLD, passed)


def make_run_record_from_bullshitbench_task(
    task: BenchmarkTask,
    *,
    model_name: str,
    policy_id: str,
    backend_name: str,
    manifest_hash: str,
    calibration_status: str,
    runner_version: str,
    seed: Optional[int] = None,
) -> RunRecord:
    """
    Crée un RunRecord partiel depuis un BenchmarkTask.

    Qualité, tokens, latence et cost_dyn sont null —
    à remplir par le runner et/ou merge_bullshitbench_judgment_into_run.
    """
    run_id = str(uuid.uuid4()).upper().replace("-", "")[:26]
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return make_run_record(
        run_id=run_id,
        timestamp_utc=timestamp,
        task_id=task.task_id,
        benchmark_id=task.benchmark_id,
        model_name=model_name,
        policy_id=policy_id,
        backend_name=backend_name,
        manifest_hash=manifest_hash,
        calibration_status=calibration_status,
        runner_version=runner_version,
        seed=seed,
        meta={
            **task.meta,
            "domain": task.domain,
            "technique": task.technique,
            "source_ref": task.source_ref,
        },
    )


def merge_bullshitbench_judgment_into_run(
    record: RunRecord,
    judgment: BenchmarkJudgment,
    *,
    overwrite: bool = False,
) -> RunRecord:
    """
    Enrichit un RunRecord avec les données qualité d'un BenchmarkJudgment.

    Lève ValueError si les task_id ne correspondent pas.
    Si overwrite=False, ne remplace pas un quality_score déjà renseigné.
    """
    if record.task_id != judgment.task_id:
        raise ValueError(
            f"task_id incompatible : record='{record.task_id}', "
            f"judgment='{judgment.task_id}'"
        )

    if record.quality_score is not None and not overwrite:
        return record

    updated_meta = {**record.meta, **judgment.meta}
    if judgment.raw_label is not None:
        updated_meta["raw_label"] = judgment.raw_label
    if judgment.judge_source is not None:
        updated_meta["judge_source"] = judgment.judge_source

    return record.model_copy(update={
        "quality_score": judgment.quality_score,
        "quality_threshold": judgment.quality_threshold,
        "passed_quality": judgment.passed_quality,
        "meta": updated_meta,
    })
