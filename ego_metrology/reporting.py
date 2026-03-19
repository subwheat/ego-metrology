"""
ego_metrology.reporting
=======================
T8 — Rapport de sprint / résumé comparatif par politique.

T8 ne mesure pas plus ; T8 rend la mesure exploitable.

Règle de recommandation par défaut :
    1. maximiser quality_pass_rate
    2. à égalité : minimiser mean_routing_regret
    3. à égalité : minimiser mean_cost_dyn
    4. à égalité : ordre lexicographique de policy_id
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from ego_metrology.logging_schema import RunRecord
from ego_metrology.regret import RegretRecord

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

REPORTING_SCHEMA_VERSION = "reporting.v1"
_NA = "n/a"


# ---------------------------------------------------------------------------
# PolicySummaryRecord
# ---------------------------------------------------------------------------

class PolicySummaryRecord(BaseModel):
    """Résumé agrégé d'une politique sur un benchmark."""

    benchmark_id: str
    policy_id: str

    # Volumétrie
    num_runs: int = 0
    num_quality_passed: int = 0
    quality_pass_rate: Optional[float] = None

    # Qualité
    mean_quality_score: Optional[float] = None

    # Coût
    mean_cost_dyn: Optional[float] = None
    median_cost_dyn: Optional[float] = None

    # Regret
    mean_routing_regret: Optional[float] = None
    median_routing_regret: Optional[float] = None
    oracle_match_rate: Optional[float] = None

    schema_version: str = Field(default=REPORTING_SCHEMA_VERSION)
    meta: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Agrégation
# ---------------------------------------------------------------------------

def build_policy_summary_records(
    runs: list[RunRecord],
    regrets: Optional[list[RegretRecord]] = None,
    *,
    benchmark_id: Optional[str] = None,
) -> list[PolicySummaryRecord]:
    """
    Construit les PolicySummaryRecord par politique.

    Args:
        runs:         RunRecord source des métriques qualité/coût.
        regrets:      RegretRecord source des métriques de regret. Optionnel.
        benchmark_id: filtre optionnel.

    Returns:
        liste de PolicySummaryRecord triée par policy_id.
    """
    if benchmark_id is not None:
        runs = [r for r in runs if r.benchmark_id == benchmark_id]

    # Grouper runs par policy_id
    run_groups: dict[str, list[RunRecord]] = defaultdict(list)
    for r in runs:
        run_groups[r.policy_id].append(r)

    # Grouper regrets par chosen_policy_id
    regret_groups: dict[str, list[RegretRecord]] = defaultdict(list)
    if regrets:
        for r in regrets:
            if benchmark_id is None or r.benchmark_id == benchmark_id:
                regret_groups[r.chosen_policy_id].append(r)

    # Déduire le benchmark_id dominant
    all_benchmark_ids = {r.benchmark_id for r in runs}
    bm_id = benchmark_id or (next(iter(all_benchmark_ids)) if all_benchmark_ids else "unknown")

    summaries: list[PolicySummaryRecord] = []
    for policy_id, policy_runs in run_groups.items():
        num_runs = len(policy_runs)
        num_passed = sum(1 for r in policy_runs if r.passed_quality is True)

        quality_scores = [r.quality_score for r in policy_runs if r.quality_score is not None]
        costs = [r.cost_dyn for r in policy_runs if r.cost_dyn is not None]

        policy_regrets = regret_groups.get(policy_id, [])
        computable = [r.routing_regret for r in policy_regrets if r.routing_regret is not None]
        oracle_matches = [
            r for r in policy_regrets
            if r.regret_status == "ok" and r.chosen_policy_id == r.oracle_policy_id
        ]
        computable_ok = [r for r in policy_regrets if r.regret_status == "ok"]

        summaries.append(PolicySummaryRecord(
            benchmark_id=bm_id,
            policy_id=policy_id,
            num_runs=num_runs,
            num_quality_passed=num_passed,
            quality_pass_rate=num_passed / num_runs if num_runs > 0 else None,
            mean_quality_score=statistics.mean(quality_scores) if quality_scores else None,
            mean_cost_dyn=statistics.mean(costs) if costs else None,
            median_cost_dyn=statistics.median(costs) if costs else None,
            mean_routing_regret=statistics.mean(computable) if computable else None,
            median_routing_regret=statistics.median(computable) if computable else None,
            oracle_match_rate=(
                len(oracle_matches) / len(computable_ok) if computable_ok else None
            ),
        ))

    return sorted(summaries, key=lambda s: s.policy_id)


# ---------------------------------------------------------------------------
# Recommandation
# ---------------------------------------------------------------------------

def _recommendation_sort_key(s: PolicySummaryRecord) -> tuple:
    """Clé de tri pour la recommandation par défaut."""
    return (
        -(s.quality_pass_rate if s.quality_pass_rate is not None else -1.0),
        s.mean_routing_regret if s.mean_routing_regret is not None else float("inf"),
        s.mean_cost_dyn if s.mean_cost_dyn is not None else float("inf"),
        s.policy_id,
    )


def _find_best(
    summaries: list[PolicySummaryRecord],
    key,
    reverse: bool = False,
) -> Optional[str]:
    valid = [s for s in summaries if key(s) is not None]
    if not valid:
        return None
    return sorted(valid, key=key, reverse=reverse)[0].policy_id


# ---------------------------------------------------------------------------
# Sprint summary
# ---------------------------------------------------------------------------

def summarize_sprint_outcome(
    policy_summaries: list[PolicySummaryRecord],
    regret_records: Optional[list[RegretRecord]] = None,
) -> dict[str, Any]:
    """Produit le résumé global du sprint."""
    if not policy_summaries:
        return {}

    benchmark_id = policy_summaries[0].benchmark_id
    num_runs_total = sum(s.num_runs for s in policy_summaries)
    num_regret = len(regret_records) if regret_records else 0

    recommended = sorted(policy_summaries, key=_recommendation_sort_key)[0]

    best_quality = _find_best(
        policy_summaries,
        key=lambda s: s.quality_pass_rate,
        reverse=True,
    )
    lowest_cost = _find_best(
        policy_summaries,
        key=lambda s: s.mean_cost_dyn,
    )
    lowest_regret = _find_best(
        policy_summaries,
        key=lambda s: s.mean_routing_regret,
    )

    # Phrase de conclusion
    parts = []
    if recommended.quality_pass_rate is not None:
        parts.append(f"pass rate {recommended.quality_pass_rate:.0%}")
    if recommended.mean_routing_regret is not None:
        parts.append(f"mean regret {recommended.mean_routing_regret:.1f}")
    if recommended.mean_cost_dyn is not None:
        parts.append(f"mean cost {recommended.mean_cost_dyn:.1f}")
    reason = (
        f"Highest quality pass rate with best overall tradeoff "
        f"({', '.join(parts)})."
        if parts else "Selected by default ranking."
    )

    return {
        "benchmark_id": benchmark_id,
        "num_policies": len(policy_summaries),
        "num_runs_total": num_runs_total,
        "num_regret_records": num_regret,
        "recommended_policy_id": recommended.policy_id,
        "recommendation_reason": reason,
        "best_quality_policy_id": best_quality,
        "lowest_cost_policy_id": lowest_cost,
        "lowest_regret_policy_id": lowest_regret,
    }


# ---------------------------------------------------------------------------
# Rendu Markdown
# ---------------------------------------------------------------------------

def _fmt(value: Any, precision: int = 2) -> str:
    if value is None:
        return _NA
    if isinstance(value, float):
        return f"{value:.{precision}f}"
    return str(value)


def render_markdown_report(
    policy_summaries: list[PolicySummaryRecord],
    sprint_summary: dict[str, Any],
    *,
    benchmark_id: str,
    title: str = "EGO Metrology Sprint Report",
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    recommended = sprint_summary.get("recommended_policy_id", _NA)
    reason = sprint_summary.get("recommendation_reason", "")

    lines: list[str] = []

    # Header
    lines += [
        f"# {title}",
        "",
        f"**Benchmark :** `{benchmark_id}`  ",
        f"**Date :** {now}  ",
        f"**Schema :** `{REPORTING_SCHEMA_VERSION}`  ",
        "",
    ]

    # Executive summary
    lines += [
        "## Executive Summary",
        "",
        f"- **Runs total :** {sprint_summary.get('num_runs_total', _NA)}",
        f"- **Policies :** {sprint_summary.get('num_policies', _NA)}",
        f"- **Regret records :** {sprint_summary.get('num_regret_records', _NA)}",
        f"- **Recommended policy :** `{recommended}`",
        f"- **Best quality policy :** `{sprint_summary.get('best_quality_policy_id', _NA)}`",
        f"- **Lowest cost policy :** `{sprint_summary.get('lowest_cost_policy_id', _NA)}`",
        f"- **Lowest regret policy :** `{sprint_summary.get('lowest_regret_policy_id', _NA)}`",
        "",
    ]

    # Tableau comparatif
    lines += [
        "## Policy Comparison",
        "",
        "| policy_id | runs | pass_rate | mean_quality | mean_cost | mean_regret | oracle_match |",
        "|-----------|------|-----------|--------------|-----------|-------------|--------------|",
    ]
    for s in policy_summaries:
        marker = " ✓" if s.policy_id == recommended else ""
        lines.append(
            f"| `{s.policy_id}`{marker} "
            f"| {s.num_runs} "
            f"| {_fmt(s.quality_pass_rate)} "
            f"| {_fmt(s.mean_quality_score)} "
            f"| {_fmt(s.mean_cost_dyn)} "
            f"| {_fmt(s.mean_routing_regret)} "
            f"| {_fmt(s.oracle_match_rate)} |"
        )
    lines.append("")

    # Recommandation
    lines += [
        "## Recommendation",
        "",
        f"**Default policy : `{recommended}`**",
        "",
        reason,
        "",
        "_Ranking rule : (1) highest pass rate, (2) lowest mean regret, "
        "(3) lowest mean cost, (4) lexicographic policy_id._",
        "",
    ]

    # Limites
    lines += [
        "## Limits",
        "",
        "- Single benchmark (`bullshitbench_v2`)",
        "- `cost_dyn` v1 is a token+latency proxy, not a real provider cost",
        "- `routing_regret` not computable where `cost_dyn` or oracle is missing",
        "- `single_pass_verify` and `cascade_small_to_large` not yet fully executable",
        "",
    ]

    return "\n".join(lines)


def write_markdown_report(path: str | Path, content: str) -> None:
    """Écrit un rapport Markdown sur disque."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Export CSV
# ---------------------------------------------------------------------------

def write_policy_summary_csv(
    path: str | Path,
    summaries: list[PolicySummaryRecord],
) -> None:
    """Exporte les PolicySummaryRecord en CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "benchmark_id", "policy_id", "num_runs", "num_quality_passed",
        "quality_pass_rate", "mean_quality_score",
        "mean_cost_dyn", "median_cost_dyn",
        "mean_routing_regret", "median_routing_regret",
        "oracle_match_rate",
    ]

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for s in summaries:
            writer.writerow({f: getattr(s, f) for f in fields})
