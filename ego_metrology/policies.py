"""
ego_metrology.policies
======================
PolicySpec + PolicyRegistry — registre canonique des politiques d'inférence.
Registry version : policy-registry.v1
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

REGISTRY_VERSION = "policy-registry.v1"


# ---------------------------------------------------------------------------
# PolicySpec
# ---------------------------------------------------------------------------

class PolicySpec(BaseModel):
    """Description déclarative d'une politique d'inférence."""

    policy_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    execution_mode: str = Field(..., min_length=1)
    verification_enabled: bool
    cascade_enabled: bool
    cascade_target: Optional[str] = None
    max_passes: int = Field(..., ge=1)
    notes: Optional[str] = None

    # ------------------------------------------------------------------
    # Cohérences croisées
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _check_cascade_target(self) -> "PolicySpec":
        """cascade_enabled ↔ cascade_target cohérence."""
        if not self.cascade_enabled and self.cascade_target is not None:
            raise ValueError(
                f"[{self.policy_id}] cascade_enabled=false "
                f"mais cascade_target='{self.cascade_target}' (attendu null)"
            )
        if self.cascade_enabled and self.cascade_target is None:
            raise ValueError(
                f"[{self.policy_id}] cascade_enabled=true "
                f"mais cascade_target est null"
            )
        return self

    @model_validator(mode="after")
    def _check_verification_passes(self) -> "PolicySpec":
        """verification_enabled=true → max_passes >= 2."""
        if self.verification_enabled and self.max_passes < 2:
            raise ValueError(
                f"[{self.policy_id}] verification_enabled=true "
                f"mais max_passes={self.max_passes} (minimum 2)"
            )
        return self

    @model_validator(mode="after")
    def _check_execution_mode_constraints(self) -> "PolicySpec":
        """Cohérences execution_mode ↔ max_passes / cascade_enabled."""
        mode = self.execution_mode
        if mode == "single_pass" and self.max_passes != 1:
            raise ValueError(
                f"[{self.policy_id}] execution_mode='single_pass' "
                f"mais max_passes={self.max_passes} (attendu 1)"
            )
        if mode == "verify_pass" and self.max_passes < 2:
            raise ValueError(
                f"[{self.policy_id}] execution_mode='verify_pass' "
                f"mais max_passes={self.max_passes} (minimum 2)"
            )
        if mode == "cascade" and not self.cascade_enabled:
            raise ValueError(
                f"[{self.policy_id}] execution_mode='cascade' "
                f"mais cascade_enabled=false"
            )
        return self


# ---------------------------------------------------------------------------
# PolicyRegistry
# ---------------------------------------------------------------------------

class PolicyRegistry(BaseModel):
    """Registre canonique des politiques d'inférence."""

    registry_version: str
    policies: list[PolicySpec] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _check_registry_version(self) -> "PolicyRegistry":
        if self.registry_version != REGISTRY_VERSION:
            raise ValueError(
                f"registry_version doit être '{REGISTRY_VERSION}', "
                f"reçu '{self.registry_version}'"
            )
        return self

    @model_validator(mode="after")
    def _check_unique_policy_ids(self) -> "PolicyRegistry":
        ids = [p.policy_id for p in self.policies]
        seen: set[str] = set()
        duplicates: list[str] = []
        for pid in ids:
            if pid in seen:
                duplicates.append(pid)
            seen.add(pid)
        if duplicates:
            raise ValueError(
                f"policy_id dupliqués dans le registre : {duplicates}"
            )
        return self


# ---------------------------------------------------------------------------
# Fonctions
# ---------------------------------------------------------------------------

def load_policy_registry(path: str | Path) -> PolicyRegistry:
    """Charge et valide un PolicyRegistry depuis un fichier JSON."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return PolicyRegistry.model_validate(data)


def get_policy(registry: PolicyRegistry, policy_id: str) -> PolicySpec:
    """Retourne la PolicySpec correspondant à policy_id.

    Lève KeyError si l'identifiant est absent du registre.
    """
    for policy in registry.policies:
        if policy.policy_id == policy_id:
            return policy
    raise KeyError(f"policy_id '{policy_id}' absent du registre")


def list_policy_ids(registry: PolicyRegistry) -> list[str]:
    """Retourne la liste ordonnée des policy_id du registre."""
    return [p.policy_id for p in registry.policies]
