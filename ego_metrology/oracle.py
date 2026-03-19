"""
ego_metrology.oracle
====================
Oracle offline C* — Ticket 6 EGO Metrology.

Pour chaque tâche, calcule la politique admissible la moins coûteuse
parmi les runs déjà produits.

Définition de C* :
    C*(task) = min cost_dyn(run)
    sur les runs tels que :
        - même task_id
        - passed_quality == True
        - cost_dyn is not None

Tie-break :
    1. cost_dyn ascendant
    2. quality_score descendant (à coût égal)
    3. policy_id lexicographique (déterminisme final)

Schema version : oracle.v1
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from ego_metrology.logging_schema import RunRecord, load_run_records_jsonl

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

ORACLE_SCHEMA_VERSION = "oracle.v1"

SelectionStatus = str  # "ok" | "no_admissible_run"


# ---------------------------------------------------------------------------
# OracleRecord
# ---------------------------------------------------------------------------

class OracleRecord(BaseModel):
    """Résultat oracle offline pour une tâche donnée."""

    # Identité
    task_id: str = Field(..., min_length=1)
    benchmark_id: str = Field(..., min_length=1)

    # Sélection
    oracle_policy_id: Optional[str] = None
    cost_star: Optional[float] = None
    oracle_quality_score: Optional[float] = None

    # Contexte de décision
    candidate_policy_ids: list[str] = Field(default_factory=list)
    admissible_policy_ids: list[str] = Field(default_factory=list)
    num_candidates: int = 0
    num_admissible: int = 0
    selection_status: str = "no_admissible_run"

    # Reproductibilité
    schema_version: str = Field(default=ORACLE_SCHEMA_VERSION)

    # Extension
    meta: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _is_admissible(run: RunRecord) -> bool:
    """Un run est admissible si passed_quality=True et cost_dyn non nul."""
    return run.passed_quality is True and run.cost_dyn is not None


def _tie_break_key(run: RunRecord) -> tuple:
    """Clé de tri pour tie-break : (cost_dyn asc, quality_score desc, policy_id asc)."""
    return (
        run.cost_dyn,
        -(run.quality_score if run.quality_score is not None else 0.0),
        run.policy_id,
    )


# ---------------------------------------------------------------------------
# Sélection par tâche
# ---------------------------------------------------------------------------

def select_oracle_run_for_task(runs: list[RunRecord]) -> OracleRecord:
    """
    Calcule l'OracleRecord pour un ensemble de runs d'une même tâche.

    Args:
        runs: liste de RunRecord — doivent tous partager le même task_id
              et le même benchmark_id.

    Returns:
        OracleRecord avec cost_star et oracle_policy_id si au moins un
        run admissible existe.

    Raises:
        ValueError si les runs mélangent des task_id ou benchmark_id différents.
    """
    if not runs:
        raise ValueError("runs ne peut pas être vide")

    # Vérifier homogénéité
    task_ids = {r.task_id for r in runs}
    if len(task_ids) > 1:
        raise ValueError(f"Runs hétérogènes — task_id multiples : {task_ids}")

    benchmark_ids = {r.benchmark_id for r in runs}
    if len(benchmark_ids) > 1:
        raise ValueError(
            f"Runs hétérogènes — benchmark_id multiples sur task_id "
            f"'{runs[0].task_id}' : {benchmark_ids}"
        )

    task_id = runs[0].task_id
    benchmark_id = runs[0].benchmark_id

    candidate_policy_ids = sorted({r.policy_id for r in runs})
    admissible_runs = [r for r in runs if _is_admissible(r)]
    admissible_policy_ids = sorted({r.policy_id for r in admissible_runs})

    if not admissible_runs:
        return OracleRecord(
            task_id=task_id,
            benchmark_id=benchmark_id,
            oracle_policy_id=None,
            cost_star=None,
            oracle_quality_score=None,
            candidate_policy_ids=candidate_policy_ids,
            admissible_policy_ids=[],
            num_candidates=len(candidate_policy_ids),
            num_admissible=0,
            selection_status="no_admissible_run",
            meta={
                "observed_policy_ids": candidate_policy_ids,
            },
        )

    # Tri tie-break
    best = sorted(admissible_runs, key=_tie_break_key)[0]

    # Déterminer si tie-break a été utilisé
    best_cost = best.cost_dyn
    runs_at_best_cost = [r for r in admissible_runs if r.cost_dyn == best_cost]
    tie_break_applied = len(runs_at_best_cost) > 1

    return OracleRecord(
        task_id=task_id,
        benchmark_id=benchmark_id,
        oracle_policy_id=best.policy_id,
        cost_star=best.cost_dyn,
        oracle_quality_score=best.quality_score,
        candidate_policy_ids=candidate_policy_ids,
        admissible_policy_ids=admissible_policy_ids,
        num_candidates=len(candidate_policy_ids),
        num_admissible=len(admissible_policy_ids),
        selection_status="ok",
        meta={
            "selected_run_id": best.run_id,
            "selected_model_name": best.model_name,
            "tie_break_applied": tie_break_applied,
            "observed_policy_ids": candidate_policy_ids,
        },
    )


# ---------------------------------------------------------------------------
# Construction pour un ensemble de runs
# ---------------------------------------------------------------------------

def build_oracle_records(
    runs: list[RunRecord],
    *,
    benchmark_id: Optional[str] = None,
) -> list[OracleRecord]:
    """
    Construit les OracleRecord pour tous les task_id observés.

    Args:
        runs:         liste de RunRecord (multi-tâches, multi-politiques).
        benchmark_id: si fourni, filtre les runs sur ce benchmark uniquement.

    Returns:
        liste d'OracleRecord triée par task_id.
    """
    if benchmark_id is not None:
        runs = [r for r in runs if r.benchmark_id == benchmark_id]

    # Grouper par task_id
    groups: dict[str, list[RunRecord]] = defaultdict(list)
    for run in runs:
        groups[run.task_id].append(run)

    records = [
        select_oracle_run_for_task(group)
        for group in groups.values()
    ]
    return sorted(records, key=lambda r: r.task_id)


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_run_records_for_oracle(path: str | Path) -> list[RunRecord]:
    """Charge des RunRecord depuis un fichier JSONL pour traitement oracle."""
    return load_run_records_jsonl(str(path))


def append_oracle_records_jsonl(
    path: str | Path,
    records: list[OracleRecord],
) -> None:
    """Écrit une liste d'OracleRecord en mode append-only dans un fichier JSONL."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for record in records:
            fh.write(record.model_dump_json() + "\n")


# ---------------------------------------------------------------------------
# Résumé global
# ---------------------------------------------------------------------------

def summarize_oracle_records(records: list[OracleRecord]) -> dict[str, Any]:
    """
    Produit un résumé agrégé des OracleRecord.

    Returns:
        dict avec couverture, coûts moyens/médians, et win counts par politique.
    """
    total = len(records)
    with_oracle = [r for r in records if r.selection_status == "ok"]
    without_admissible = [r for r in records if r.selection_status == "no_admissible_run"]

    cost_stars = [r.cost_star for r in with_oracle if r.cost_star is not None]

    win_counts: dict[str, int] = defaultdict(int)
    for r in with_oracle:
        if r.oracle_policy_id is not None:
            win_counts[r.oracle_policy_id] += 1

    return {
        "num_tasks_total": total,
        "num_tasks_with_oracle": len(with_oracle),
        "num_tasks_without_admissible_run": len(without_admissible),
        "oracle_coverage": len(with_oracle) / total if total > 0 else 0.0,
        "mean_cost_star": statistics.mean(cost_stars) if cost_stars else None,
        "median_cost_star": statistics.median(cost_stars) if cost_stars else None,
        "oracle_policy_win_counts": dict(win_counts),
    }
