"""
ego_metrology.heuristics
~~~~~~~~~~~~~~~~~~~~~~~~
Configurable heuristic formulas and thresholds derived from EGO V12.2 theory.

All values here are defaults. They can be overridden without forking the project
by passing custom parameters to the compute_* functions.

Geometric constants:
    R_1D   ≈ 1.2071  — quasi-linear regime lower bound
    R_HOLO ≈ 1.5708  — holographic saturation upper bound (π/2)
"""

from __future__ import annotations
import math

# ── Geometric constants (EGO V12.2) ──────────────────────────────────────────

R_1D   = (1 + math.sqrt(2)) / 2   # ≈ 1.2071
R_HOLO = math.pi / 2               # ≈ 1.5708

# ── Saturation thresholds ─────────────────────────────────────────────────────

THRESHOLD_WARNING  = 1.45
THRESHOLD_CRITICAL = 1.55

# ── Heuristic formulas ────────────────────────────────────────────────────────

def compute_eta(tokens: int, max_context: int) -> float:
    """
    Compute normalised context pressure η ∈ [0, 1].

    η = tokens / max_context, clamped to [0, 1].
    η = 0 means empty context; η = 1 means fully saturated window.

    Args:
        tokens:      Number of tokens in the prompt.
        max_context: Maximum context window size for the model.

    Returns:
        float: η ∈ [0, 1]
    """
    return min(max(tokens / max_context, 0.0), 1.0)


def compute_alpha_s(eta: float, exponent: float = 1.5) -> float:
    """
    Compute spectatorization ratio α_S ∈ [0, 1].

    Heuristic proxy for the HQEC k/n coding rate.
    α_S → 0 means efficient encoding (low passive load).
    α_S → 1 means the model bears full structural weight of the context.

    EGO V12.2 proxy: α_S = η^exponent

    Args:
        eta:      Normalised context pressure (output of compute_eta).
        exponent: Controls how fast passive load grows. Default 1.5 (EGO V12.2).

    Returns:
        float: α_S ∈ [0, 1]
    """
    return round(eta ** exponent, 6)


def compute_r_eta(eta: float) -> float:
    """
    Compute geometric position r(η) on the 1D → holographic continuum.

    EGO V12.2 equation: r(η) = r_1D + (π/2 − r_1D) · η

    r(η) ≈ 1.2071 : quasi-linear regime, attention processes tokens efficiently.
    r(η) ≈ 1.5708 : holographic bound, adding tokens yields no further gain.

    Args:
        eta: Normalised context pressure ∈ [0, 1].

    Returns:
        float: r(η) ∈ [R_1D, R_HOLO]
    """
    return round(R_1D + (R_HOLO - R_1D) * eta, 6)


def compute_geometric_status(r_eta: float) -> str:
    """
    Classify the geometric regime from r(η).

    Returns:
        "Safe"     if r(η) ≤ 1.45
        "Warning"  if 1.45 < r(η) < 1.55
        "Critical" if r(η) ≥ 1.55
    """
    if r_eta >= THRESHOLD_CRITICAL:
        return "Critical"
    if r_eta > THRESHOLD_WARNING:
        return "Warning"
    return "Safe"


def compute_c_dyn(tokens: int, c_conf_base: float, alpha_s: float) -> float:
    """
    Compute dynamic contextual cost C_dyn.

    EGO V12.2 equation: C_dyn = tokens · c_conf_base · (1 + α_S)

    Args:
        tokens:       Number of tokens in the prompt.
        c_conf_base:  Baseline confinement cost (sectoral anchor).
        alpha_s:      Spectatorization ratio α_S.

    Returns:
        float: C_dyn ≥ 0
    """
    return round((tokens * c_conf_base) * (1 + alpha_s), 4)


def compute_log_tau(a_secteur: float, beta_secteur: float, c_dyn: float) -> float:
    """
    Compute log of logical decay lifespan τ.

    EGO V12.2 sectoral stability law: log τ = a_secteur − β_secteur · C_dyn
    Clamped to [1, 10] → τ ∈ [3, 22_026] tokens.

    Note: Meaningful τ values require empirically calibrated a_secteur and
    beta_secteur. OSS presets use placeholder constants — see EGO Enterprise.

    Args:
        a_secteur:    Base stability constant (sectoral anchor).
        beta_secteur: Dissipation rate (sectoral anchor).
        c_dyn:        Dynamic contextual cost.

    Returns:
        float: log τ ∈ [1, 10]
    """
    return max(1.0, min(a_secteur - beta_secteur * c_dyn, 10.0))
