"""
ego_metrology.regret
====================
routing_regret v1 — Ticket 7 EGO Metrology.

Définition :
    routing_regret = chosen_cost_dyn - cost_star

T6 dit quel choix était optimal offline.
T7 mesure combien le choix réellement évalué s'en écarte.

Schema version : routing-regret.v1
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from ego_metrology.logging_schema import RunRecord
from ego_metrology.oracle import OracleRecord

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

REGRET_SCHEMA_VERSION = "routing-regret.v1"


# ---------------------------------------------------------------------------
# RegretRecord
# ---------------------------------------------------------------------------

class RegretRecord(BaseModel):
    """Enregistrement canonique du regret de routage pour une décision."""

    # Identité
    task_id: str = Field(..., min_length=1)
    benchmark_id: str = Field(..., min_length=1)

    # Décision
    chosen_policy_id: str = Field(..., min_length=1)
    oracle_policy_id: Optional[str] = None

    # Coûts
    chosen_cost_dyn: Optional[float] = None
    cost_star: Optional[float] = None
    routing_regret: Optional[float] = None

    # Qualité du choix
    chosen_passed_quality: Optional[bool] = None

    # Statut
    oracle_available: bool = False
    regret_status: str = "no_oracle"

    # Reproductibilité
    schema_version: str = Field(default=REGRET_SCHEMA_VERSION)

    # Extension
    meta: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Calcul élémentaire
# ---------------------------------------------------------------------------

def compute_routing_regret(
    *,
    chosen_cost_dyn: Optional[float],
    cost_star: Optional[float],
) -> Optional[float]:
    """
    Calcule routing_regret = chosen_cost_dyn - cost_star.

    Retourne None si l'un des deux est absent.
    """
    if chosen_cost_dyn is None or cost_star is None:
        return None
    return chosen_cost_dyn - cost_star


# ---------------------------------------------------------------------------
# Construction d'un RegretRecord
# ---------------------------------------------------------------------------

def make_regret_record(
    chosen_run: RunRecord,
    oracle_record: Optional[OracleRecord],
) -> RegretRecord:
    """
    Construit un RegretRecord pour un run choisi et son oracle associé.

    Args:
        chosen_run:    RunRecord du choix à évaluer.
        oracle_record: OracleRecord correspondant au même task_id, ou None.

    Returns:
        RegretRecord avec routing_regret calculé si possible.
    """
    task_id = chosen_run.task_id
    benchmark_id = chosen_run.benchmark_id
    chosen_policy_id = chosen_run.policy_id
    chosen_cost_dyn = chosen_run.cost_dyn
    chosen_passed_quality = chosen_run.passed_quality

    # Cas : oracle absent
    if oracle_record is None:
        return RegretRecord(
            task_id=task_id,
            benchmark_id=benchmark_id,
            chosen_policy_id=chosen_policy_id,
            oracle_policy_id=None,
            chosen_cost_dyn=chosen_cost_dyn,
            cost_star=None,
            routing_regret=None,
            chosen_passed_quality=chosen_passed_quality,
            oracle_available=False,
            regret_status="no_oracle",
            meta={
                "chosen_run_id": chosen_run.run_id,
                "oracle_selection_status": None,
                "negative_regret_detected": False,
                "delta_vs_oracle_policy": None,
            },
        )

    # Cas : task_id mismatch
    if oracle_record.task_id != task_id:
        raise ValueError(
            f"task_id incompatible : run='{task_id}', "
            f"oracle='{oracle_record.task_id}'"
        )

    # Cas : mismatch benchmark
    if oracle_record.benchmark_id != benchmark_id:
        return RegretRecord(
            task_id=task_id,
            benchmark_id=benchmark_id,
            chosen_policy_id=chosen_policy_id,
            oracle_policy_id=oracle_record.oracle_policy_id,
            chosen_cost_dyn=chosen_cost_dyn,
            cost_star=None,
            routing_regret=None,
            chosen_passed_quality=chosen_passed_quality,
            oracle_available=False,
            regret_status="benchmark_mismatch",
            meta={
                "chosen_run_id": chosen_run.run_id,
                "oracle_selection_status": oracle_record.selection_status,
                "negative_regret_detected": False,
                "delta_vs_oracle_policy": None,
            },
        )

    # Cas : oracle sans cost_star
    if oracle_record.cost_star is None or oracle_record.selection_status != "ok":
        return RegretRecord(
            task_id=task_id,
            benchmark_id=benchmark_id,
            chosen_policy_id=chosen_policy_id,
            oracle_policy_id=oracle_record.oracle_policy_id,
            chosen_cost_dyn=chosen_cost_dyn,
            cost_star=None,
            routing_regret=None,
            chosen_passed_quality=chosen_passed_quality,
            oracle_available=False,
            regret_status="no_oracle",
            meta={
                "chosen_run_id": chosen_run.run_id,
                "oracle_selection_status": oracle_record.selection_status,
                "negative_regret_detected": False,
                "delta_vs_oracle_policy": None,
            },
        )

    # Cas : coût choisi manquant
    if chosen_cost_dyn is None:
        return RegretRecord(
            task_id=task_id,
            benchmark_id=benchmark_id,
            chosen_policy_id=chosen_policy_id,
            oracle_policy_id=oracle_record.oracle_policy_id,
            chosen_cost_dyn=None,
            cost_star=oracle_record.cost_star,
            routing_regret=None,
            chosen_passed_quality=chosen_passed_quality,
            oracle_available=True,
            regret_status="chosen_cost_missing",
            meta={
                "chosen_run_id": chosen_run.run_id,
                "oracle_selection_status": oracle_record.selection_status,
                "negative_regret_detected": False,
                "delta_vs_oracle_policy": None,
            },
        )

    # Cas nominal : calcul du regret
    cost_star = oracle_record.cost_star
    regret = compute_routing_regret(
        chosen_cost_dyn=chosen_cost_dyn,
        cost_star=cost_star,
    )
    negative_regret = regret is not None and regret < 0
    delta = (
        "same_policy"
        if chosen_policy_id == oracle_record.oracle_policy_id
        else "different_policy"
    )

    return RegretRecord(
        task_id=task_id,
        benchmark_id=benchmark_id,
        chosen_policy_id=chosen_policy_id,
        oracle_policy_id=oracle_record.oracle_policy_id,
        chosen_cost_dyn=chosen_cost_dyn,
        cost_star=cost_star,
        routing_regret=regret,
        chosen_passed_quality=chosen_passed_quality,
        oracle_available=True,
        regret_status="ok",
        meta={
            "chosen_run_id": chosen_run.run_id,
            "oracle_selection_status": oracle_record.selection_status,
            "negative_regret_detected": negative_regret,
            "delta_vs_oracle_policy": delta,
        },
    )


# ---------------------------------------------------------------------------
# Construction pour un ensemble
# ---------------------------------------------------------------------------

def build_regret_records(
    chosen_runs: list[RunRecord],
    oracle_records: list[OracleRecord],
) -> list[RegretRecord]:
    """
    Construit les RegretRecord pour tous les runs fournis.

    Args:
        chosen_runs:    Runs à évaluer (tous traités comme "choisis").
        oracle_records: OracleRecord de référence, indexés par task_id.

    Returns:
        liste de RegretRecord triée par task_id.
    """
    oracle_index: dict[str, OracleRecord] = {}
    for r in oracle_records:
        if r.task_id in oracle_index:
            raise ValueError(
                f"OracleRecord dupliqué pour task_id '{r.task_id}' — "
                f"les oracle_records doivent être uniques par task_id"
            )
        oracle_index[r.task_id] = r
    records = [
        make_regret_record(run, oracle_index.get(run.task_id))
        for run in chosen_runs
    ]
    return sorted(records, key=lambda r: r.task_id)


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def append_regret_records_jsonl(
    path: str | Path,
    records: list[RegretRecord],
) -> None:
    """Écrit une liste de RegretRecord en mode append-only dans un fichier JSONL."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for record in records:
            fh.write(record.model_dump_json() + "\n")


# ---------------------------------------------------------------------------
# Résumé global
# ---------------------------------------------------------------------------

def summarize_regret_records(records: list[RegretRecord]) -> dict[str, Any]:
    """
    Produit un résumé agrégé des RegretRecord.
    """
    total = len(records)
    computable = [r for r in records if r.regret_status == "ok"]
    regrets = [r.routing_regret for r in computable if r.routing_regret is not None]

    num_no_oracle = sum(1 for r in records if r.regret_status == "no_oracle")
    num_cost_missing = sum(1 for r in records if r.regret_status == "chosen_cost_missing")
    num_mismatch = sum(1 for r in records if r.regret_status == "benchmark_mismatch")
    num_zero = sum(1 for v in regrets if v == 0.0)
    num_negative = sum(1 for v in regrets if v < 0)

    policy_counts: dict[str, int] = defaultdict(int)
    for r in records:
        policy_counts[r.chosen_policy_id] += 1

    oracle_matches = sum(
        1 for r in computable
        if r.chosen_policy_id == r.oracle_policy_id
    )
    oracle_match_rate = oracle_matches / len(computable) if computable else None

    return {
        "num_records_total": total,
        "num_regret_computable": len(computable),
        "num_no_oracle": num_no_oracle,
        "num_chosen_cost_missing": num_cost_missing,
        "num_benchmark_mismatch": num_mismatch,
        "mean_routing_regret": statistics.mean(regrets) if regrets else None,
        "median_routing_regret": statistics.median(regrets) if regrets else None,
        "p90_routing_regret": (
            sorted(regrets)[int(len(regrets) * 0.9)] if regrets else None
        ),
        "num_zero_regret": num_zero,
        "num_negative_regret": num_negative,
        "min_routing_regret": min(regrets) if regrets else None,
        "chosen_policy_counts": dict(policy_counts),
        "oracle_match_rate": oracle_match_rate,
    }
