"""
ego_metrology.backends.base
===========================
Protocole backend minimal pour T5/T9.

Un backend reçoit un prompt + contexte d'exécution
et retourne un BackendResult avec les observables mesurés.

T9.2 :
- extension du contrat BackendResult vers un runtime v2 compatible
- compatibilité conservée avec latency_ms / backend_meta
- métriques fines optionnelles pour LLM locaux / infra instrumentée
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Runtime metric provenance
# ---------------------------------------------------------------------------

MetricsSource = Literal[
    "observed_local",
    "provider_reported",
    "derived",
    "none",
]


# ---------------------------------------------------------------------------
# BackendResult
# ---------------------------------------------------------------------------

class BackendResult(BaseModel):
    """Résultat observable retourné par un backend d'exécution."""

    # --- Réponse brute ---
    response_text: Optional[str] = None

    # --- Socle portable cross-LLM ---
    provider_name: Optional[str] = None
    metrics_source: Optional[MetricsSource] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    # --- Latence ---
    latency_ms: Optional[float] = None
    latency_total_ms: Optional[float] = None

    # --- Métriques fines optionnelles ---
    prefill_ms: Optional[float] = None
    decode_ms: Optional[float] = None
    queue_ms: Optional[float] = None

    peak_vram_gb: Optional[float] = None
    gpu_power_w: Optional[float] = None
    gpu_memory_used_mb: Optional[float] = None
    gpu_utilization_pct: Optional[float] = None

    tools_count: Optional[int] = None
    loops_count: Optional[int] = None

    # --- Extension sûre ---
    backend_meta: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _fill_total_tokens(self) -> "BackendResult":
        """Auto-remplit total_tokens si prompt_tokens et completion_tokens sont présents."""
        if (
            self.prompt_tokens is not None
            and self.completion_tokens is not None
            and self.total_tokens is None
        ):
            self.total_tokens = self.prompt_tokens + self.completion_tokens
        return self

    @model_validator(mode="after")
    def _check_total_tokens(self) -> "BackendResult":
        """Vérifie la cohérence de total_tokens quand toutes les valeurs sont présentes."""
        if self.prompt_tokens is not None and self.completion_tokens is not None:
            expected = self.prompt_tokens + self.completion_tokens
            if self.total_tokens is not None and self.total_tokens != expected:
                raise ValueError(
                    f"total_tokens incohérent : {self.prompt_tokens} + "
                    f"{self.completion_tokens} = {expected}, reçu {self.total_tokens}"
                )
        return self

    @model_validator(mode="after")
    def _sync_total_latency(self) -> "BackendResult":
        """Synchronise latency_ms et latency_total_ms en compatibilité v1/v2."""
        if self.latency_ms is None and self.latency_total_ms is not None:
            self.latency_ms = self.latency_total_ms
        if self.latency_total_ms is None and self.latency_ms is not None:
            self.latency_total_ms = self.latency_ms
        return self


# ---------------------------------------------------------------------------
# Protocole backend
# ---------------------------------------------------------------------------

class GenerationBackend:
    """
    Classe de base pour les backends d'exécution.

    Sous-classer et implémenter `generate()`.
    """

    def generate(
        self,
        *,
        prompt: str,
        model_name: str,
        policy_id: str,
        seed: Optional[int] = None,
    ) -> BackendResult:
        raise NotImplementedError(
            f"{self.__class__.__name__} doit implémenter generate()"
        )


# ---------------------------------------------------------------------------
# FakeBackend — pour tests et dry_run
# ---------------------------------------------------------------------------

class FakeBackend(GenerationBackend):
    """
    Backend déterministe pour tests et développement.

    Retourne des valeurs fixes sans appel réseau.
    """

    def __init__(
        self,
        response_text: str = "This premise does not appear to be valid.",
        prompt_tokens: int = 120,
        completion_tokens: int = 48,
        latency_ms: float = 250.0,
        provider_name: str = "fake",
        metrics_source: MetricsSource = "derived",
    ) -> None:
        self._response_text = response_text
        self._prompt_tokens = prompt_tokens
        self._completion_tokens = completion_tokens
        self._latency_ms = latency_ms
        self._provider_name = provider_name
        self._metrics_source = metrics_source

    def generate(
        self,
        *,
        prompt: str,
        model_name: str,
        policy_id: str,
        seed: Optional[int] = None,
    ) -> BackendResult:
        return BackendResult(
            response_text=self._response_text,
            provider_name=self._provider_name,
            metrics_source=self._metrics_source,
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
            total_tokens=self._prompt_tokens + self._completion_tokens,
            latency_ms=self._latency_ms,
            latency_total_ms=self._latency_ms,
            backend_meta={
                "backend": "fake",
                "model_name": model_name,
                "policy_id": policy_id,
                "seed": seed,
            },
        )
