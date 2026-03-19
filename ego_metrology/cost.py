"""
ego_metrology.cost
==================
cost_dyn v1 — canonical relative execution cost.

Formule :
    cost_dyn = w_tokens * total_tokens + w_latency * latency_ms

Ce n'est pas un coût USD, ni énergétique, ni GPU.
C'est un coût canonique interne comparable entre politiques.

Cost schema version : cost-dyn.v1
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ego_metrology.logging_schema import RunRecord


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

COST_DYN_SCHEMA_VERSION = "cost-dyn.v1"
DEFAULT_W_TOKENS: float = 1.0
DEFAULT_W_LATENCY: float = 0.001


# ---------------------------------------------------------------------------
# Fonctions
# ---------------------------------------------------------------------------

def compute_cost_dyn(
    total_tokens: Optional[int],
    latency_ms: Optional[float],
    *,
    w_tokens: float = DEFAULT_W_TOKENS,
    w_latency: float = DEFAULT_W_LATENCY,
) -> Optional[float]:
    """
    Calcule le coût canonique v1 d'un run.

    Retourne None si total_tokens ou latency_ms est absent.
    Lève ValueError si une valeur est négative.

    Args:
        total_tokens:  nombre total de tokens du run (prompt + completion).
        latency_ms:    latence totale observée en millisecondes.
        w_tokens:      poids du signal tokens (défaut : 1.0).
        w_latency:     poids du signal latence (défaut : 0.001).

    Returns:
        float cost_dyn, ou None si données insuffisantes.
    """
    # Validation des poids
    if w_tokens < 0:
        raise ValueError(f"w_tokens doit être >= 0, reçu {w_tokens}")
    if w_latency < 0:
        raise ValueError(f"w_latency doit être >= 0, reçu {w_latency}")

    # Données manquantes → None (R1 : pas de calcul partiel silencieux)
    if total_tokens is None or latency_ms is None:
        return None

    # Validation des entrées
    if total_tokens < 0:
        raise ValueError(f"total_tokens doit être >= 0, reçu {total_tokens}")
    if latency_ms < 0:
        raise ValueError(f"latency_ms doit être >= 0, reçu {latency_ms}")

    return w_tokens * total_tokens + w_latency * latency_ms


def compute_cost_dyn_from_run(record: "RunRecord") -> Optional[float]:
    """
    Calcule cost_dyn depuis les champs d'un RunRecord existant.

    Utilise les poids v1 par défaut.
    """
    return compute_cost_dyn(
        total_tokens=record.total_tokens,
        latency_ms=record.latency_ms,
    )


def with_computed_cost_dyn(
    record: "RunRecord",
    *,
    overwrite: bool = False,
) -> "RunRecord":
    """
    Retourne un nouveau RunRecord enrichi avec cost_dyn calculé.

    Args:
        record:    RunRecord source (non muté).
        overwrite: si False (défaut), conserve cost_dyn existant.
                   si True, recalcule même si cost_dyn est déjà renseigné.

    Returns:
        Nouveau RunRecord avec cost_dyn rempli si calculable.
    """
    if record.cost_dyn is not None and not overwrite:
        return record

    new_cost = compute_cost_dyn_from_run(record)
    return record.model_copy(update={"cost_dyn": new_cost})
