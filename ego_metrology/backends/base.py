"""
ego_metrology.backends.base
===========================
Protocole backend minimal pour T5.

Un backend reçoit un prompt + contexte d'exécution
et retourne un BackendResult avec les observables mesurés.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# BackendResult
# ---------------------------------------------------------------------------

class BackendResult(BaseModel):
    """Résultat observable retourné par un backend d'exécution."""

    response_text: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    latency_ms: Optional[float] = None
    backend_meta: dict[str, Any] = Field(default_factory=dict)


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
    ) -> None:
        self._response_text = response_text
        self._prompt_tokens = prompt_tokens
        self._completion_tokens = completion_tokens
        self._latency_ms = latency_ms

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
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
            latency_ms=self._latency_ms,
            backend_meta={
                "backend": "fake",
                "model_name": model_name,
                "policy_id": policy_id,
                "seed": seed,
            },
        )
