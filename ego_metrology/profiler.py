from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Literal
from .heuristics import (
    compute_eta, compute_alpha_s, compute_r_eta,
    compute_geometric_status, compute_c_dyn, compute_log_tau,
    R_1D, R_HOLO
)

CalibrationStatus = Literal["heuristic", "calibrated"]

@dataclass
class ModelSectorConfig:
    name: str
    max_context_tokens: int
    a_secteur: float
    beta_secteur: float
    c_conf_base: float = 0.3
    calibration_status: CalibrationStatus = "heuristic"

# Heuristic presets — context-window driven only.
# These are NOT empirically calibrated per model.
# Production-validated sectoral anchors: julien@uyuni.world
SECTOR_CONFIGS: dict[str, ModelSectorConfig] = {
    "mistral-7b":   ModelSectorConfig("Mistral-7B",    8_192,   1.0, 0.001, calibration_status="heuristic"),
    "deepseek-14b": ModelSectorConfig("DeepSeek-14B",  16_384,  1.0, 0.001, calibration_status="heuristic"),
    "qwen-local":   ModelSectorConfig("Qwen-Local",    32_768,  1.0, 0.001, calibration_status="heuristic"),
    "claude-api":   ModelSectorConfig("Claude-API",    200_000, 1.0, 0.001, calibration_status="heuristic"),
}

GeometricStatus = Literal["Safe", "Warning", "Critical"]

@dataclass
class ProfileResult:
    model: str
    prompt_tokens: int
    max_context_tokens: int
    alpha_s: float
    eta: float
    r_eta: float
    geometric_regime: GeometricStatus
    tau: int
    c_dyn: float
    calibration_status: CalibrationStatus = "heuristic"
    r_1d: float   = field(default=R_1D)
    r_holo: float = field(default=R_HOLO)

    @property
    def saturation_pct(self):
        return round(self.prompt_tokens / self.max_context_tokens * 100, 1)

    def summary(self):
        icon = {"Safe": "✓", "Warning": "△", "Critical": "✗"}[self.geometric_regime]
        label = (
            "Heavy structural overhead" if self.alpha_s > 0.7 else
            "Moderate spectatorization" if self.alpha_s > 0.3 else
            "Efficient — low passive load"
        )
        tau_line = (
            "uncalibrated — EGO Enterprise only"
            if self.calibration_status == "heuristic"
            else f"{self.tau:,} tokens"
        )
        return f"""
  ╔═══ EGO METROLOGY v0.1.0 ═══════════════════════╗
  ║  Model        : {self.model}
  ║  Tokens       : {self.prompt_tokens:>8,} / {self.max_context_tokens:,} ({self.saturation_pct}% full)
  ║  Calibration  : {self.calibration_status}
  ╠═════════════════════════════════════════════════╣
  ║  [1] α_S  : {self.alpha_s:.6f}  — {label}
  ║  [2] r(η) : {self.r_eta:.6f}  {icon} {self.geometric_regime}
  ║  [3] τ    : {tau_line}
  ╚═════════════════════════════════════════════════╝"""


def _validate_prompt_tokens(prompt_tokens: int, max_context_tokens: int) -> None:
    if not isinstance(prompt_tokens, int):
        raise TypeError(
            f"prompt_tokens must be an integer, got {type(prompt_tokens).__name__}."
        )
    if prompt_tokens <= 0:
        raise ValueError(
            f"prompt_tokens must be > 0, got {prompt_tokens}."
        )
    if prompt_tokens > max_context_tokens:
        raise ValueError(
            f"prompt_tokens ({prompt_tokens:,}) exceeds max_context_tokens "
            f"({max_context_tokens:,}) for this model. Trim your context."
        )


class EgoProfiler:
    def __init__(self, model: str | ModelSectorConfig):
        if isinstance(model, str):
            if model not in SECTOR_CONFIGS:
                raise ValueError(
                    f"Unknown model '{model}'. "
                    f"Available: {list(SECTOR_CONFIGS.keys())}"
                )
            self.config = SECTOR_CONFIGS[model]
        else:
            self.config = model

    def _eta(self, tokens: int) -> float:
        return compute_eta(tokens, self.config.max_context_tokens)

    def get_spectatorization_ratio(self, tokens: int) -> float:
        _validate_prompt_tokens(tokens, self.config.max_context_tokens)
        return compute_alpha_s(self._eta(tokens))

    def get_geometric_saturation(self, tokens: int) -> dict:
        _validate_prompt_tokens(tokens, self.config.max_context_tokens)
        eta   = self._eta(tokens)
        r_eta = compute_r_eta(eta)
        return {
            "r_eta":  r_eta,
            "eta":    round(eta, 6),
            "status": compute_geometric_status(r_eta),
            "r_1d":   R_1D,
            "r_holo": R_HOLO,
        }

    def estimate_logical_decay(self, tokens: int) -> tuple[int, float]:
        _validate_prompt_tokens(tokens, self.config.max_context_tokens)
        alpha_s = self.get_spectatorization_ratio(tokens)
        c_dyn   = compute_c_dyn(tokens, self.config.c_conf_base, alpha_s)
        log_tau = compute_log_tau(self.config.a_secteur, self.config.beta_secteur, c_dyn)
        return int(math.exp(log_tau)), c_dyn

    def profile(self, prompt_tokens: int) -> ProfileResult:
        _validate_prompt_tokens(prompt_tokens, self.config.max_context_tokens)
        geom       = self.get_geometric_saturation(prompt_tokens)
        alpha_s    = self.get_spectatorization_ratio(prompt_tokens)
        tau, c_dyn = self.estimate_logical_decay(prompt_tokens)
        return ProfileResult(
            model=self.config.name,
            prompt_tokens=prompt_tokens,
            max_context_tokens=self.config.max_context_tokens,
            alpha_s=alpha_s,
            eta=geom["eta"],
            r_eta=geom["r_eta"],
            geometric_regime=geom["status"],
            tau=tau,
            c_dyn=c_dyn,
            calibration_status=self.config.calibration_status,
        )
