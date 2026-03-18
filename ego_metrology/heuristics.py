"""
ego_metrology.heuristics
~~~~~~~~~~~~~~~~~~~~~~~~
Configurable heuristic formulas and thresholds.

All values here are defaults derived from EGO V12.2 theory.
They can be overridden without forking the project.
"""

from __future__ import annotations
import math

# ── Geometric constants ───────────────────────────────────────────────────────

R_1D   = (1 + math.sqrt(2)) / 2   # ≈ 1.2071 — quasi-linear regime
R_HOLO = math.pi / 2               # ≈ 1.5708 — holographic saturation bound

# ── Saturation thresholds ─────────────────────────────────────────────────────

THRESHOLD_WARNING  = 1.45   # r(η) above this → Warning
THRESHOLD_CRITICAL = 1.55   # r(η) above this → Critical

# ── Heuristic formulas ────────────────────────────────────────────────────────

def compute_eta(tokens: int, max_context: int) -> float:
    """Normalised context pressure η ∈ [0, 1]."""
    return min(max(tokens / max_context, 0.0), 1.0)

def compute_alpha_s(eta: float, exponent: float = 1.5) -> float:
    """
    Spectatorization ratio α_S.
    Exponent controls how fast passive load grows with context pressure.
    Default 1.5 derived from EGO V12.2 k/n HQEC proxy.
    """
    return round(eta ** exponent, 6)

def compute_r_eta(eta: float) -> float:
    """
    Geometric position r(η) on the 1D → holographic continuum.
    EGO V12.2: r(η) = r_1D + (π/2 − r_1D) · η
    """
    return round(R_1D + (R_HOLO - R_1D) * eta, 6)

def compute_geometric_status(r_eta: float) -> str:
    """Classify geometric regime from r(η) value."""
    if r_eta >= THRESHOLD_CRITICAL:
        return "Critical"
    if r_eta > THRESHOLD_WARNING:
        return "Warning"
    return "Safe"

def compute_c_dyn(tokens: int, c_conf_base: float, alpha_s: float) -> float:
    """
    Dynamic contextual cost C_dyn.
    EGO V12.2: C_dyn = tokens · c_conf_base · (1 + α_S)
    """
    return round((tokens * c_conf_base) * (1 + alpha_s), 4)

def compute_log_tau(a_secteur: float, beta_secteur: float, c_dyn: float) -> float:
    """
    Log of logical decay lifespan τ.
    EGO V12.2: log τ = a_secteur − β_secteur · C_dyn
    Clamped to [1, 10] → τ ∈ [3, 22_026] tokens.
    """
    return max(1.0, min(a_secteur - beta_secteur * c_dyn, 10.0))
