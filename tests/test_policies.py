"""
tests/test_policies.py
======================
Tests unitaires pour PolicySpec + PolicyRegistry — Ticket 2 EGO Metrology.

Couvre tous les critères d'acceptation :
1.  charge un registre valide
2.  refuse registry_version invalide
3.  refuse policy_id dupliqué
4.  refuse policy_id vide
5.  refuse description vide
6.  refuse max_passes < 1
7.  refuse cascade_enabled=false avec cascade_target non nul
8.  refuse cascade_enabled=true avec cascade_target=null
9.  refuse verification_enabled=true avec max_passes < 2
10. get_policy("single_pass") retourne le bon objet
11. cohérences execution_mode
12. list_policy_ids
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from ego_metrology.policies import (
    REGISTRY_VERSION,
    PolicyRegistry,
    PolicySpec,
    get_policy,
    list_policy_ids,
    load_policy_registry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_policy(**kwargs) -> dict:
    """Retourne un dict PolicySpec valide, surchargeable."""
    base = dict(
        policy_id="single_pass",
        description="Single generation pass.",
        execution_mode="single_pass",
        verification_enabled=False,
        cascade_enabled=False,
        cascade_target=None,
        max_passes=1,
        notes=None,
    )
    base.update(kwargs)
    return base


def make_registry(policies: list[dict] | None = None) -> dict:
    """Retourne un dict PolicyRegistry valide avec 1 politique par défaut."""
    return {
        "registry_version": REGISTRY_VERSION,
        "policies": policies or [make_policy()],
    }


REGISTRY_JSON_PATH = Path(__file__).parent.parent / "ego_metrology" / "policy_registry.json"


# ---------------------------------------------------------------------------
# 1. Registre valide
# ---------------------------------------------------------------------------

class TestValidRegistry:
    def test_load_canonical_json(self):
        registry = load_policy_registry(REGISTRY_JSON_PATH)
        assert registry.registry_version == REGISTRY_VERSION
        assert len(registry.policies) == 3

    def test_canonical_contains_three_policies(self):
        registry = load_policy_registry(REGISTRY_JSON_PATH)
        ids = list_policy_ids(registry)
        assert "single_pass" in ids
        assert "single_pass_verify" in ids
        assert "cascade_small_to_large" in ids

    def test_policy_spec_fields(self):
        registry = load_policy_registry(REGISTRY_JSON_PATH)
        sp = get_policy(registry, "single_pass")
        assert sp.execution_mode == "single_pass"
        assert sp.verification_enabled is False
        assert sp.cascade_enabled is False
        assert sp.max_passes == 1

    def test_single_pass_verify_fields(self):
        registry = load_policy_registry(REGISTRY_JSON_PATH)
        spv = get_policy(registry, "single_pass_verify")
        assert spv.verification_enabled is True
        assert spv.max_passes == 2
        assert spv.cascade_enabled is False

    def test_cascade_fields(self):
        registry = load_policy_registry(REGISTRY_JSON_PATH)
        c = get_policy(registry, "cascade_small_to_large")
        assert c.cascade_enabled is True
        assert c.cascade_target == "large_model"
        assert c.execution_mode == "cascade"


# ---------------------------------------------------------------------------
# 2. Refus registry_version invalide
# ---------------------------------------------------------------------------

class TestRegistryVersion:
    def test_wrong_version_raises(self):
        data = make_registry()
        data["registry_version"] = "policy-registry.v0"
        with pytest.raises(ValidationError, match="registry_version"):
            PolicyRegistry.model_validate(data)

    def test_empty_version_raises(self):
        data = make_registry()
        data["registry_version"] = ""
        with pytest.raises(ValidationError):
            PolicyRegistry.model_validate(data)


# ---------------------------------------------------------------------------
# 3. Refus policy_id dupliqué
# ---------------------------------------------------------------------------

class TestDuplicatePolicyId:
    def test_duplicate_raises(self):
        policies = [make_policy(policy_id="single_pass"), make_policy(policy_id="single_pass")]
        with pytest.raises(ValidationError, match="dupliqués"):
            PolicyRegistry.model_validate(make_registry(policies))

    def test_distinct_ids_accepted(self):
        policies = [
            make_policy(policy_id="single_pass"),
            make_policy(policy_id="other_pass"),
        ]
        registry = PolicyRegistry.model_validate(make_registry(policies))
        assert len(registry.policies) == 2


# ---------------------------------------------------------------------------
# 4. Refus policy_id vide
# ---------------------------------------------------------------------------

class TestEmptyPolicyId:
    def test_empty_policy_id_raises(self):
        with pytest.raises(ValidationError):
            PolicySpec(**make_policy(policy_id=""))


# ---------------------------------------------------------------------------
# 5. Refus description vide
# ---------------------------------------------------------------------------

class TestEmptyDescription:
    def test_empty_description_raises(self):
        with pytest.raises(ValidationError):
            PolicySpec(**make_policy(description=""))


# ---------------------------------------------------------------------------
# 6. Refus max_passes < 1
# ---------------------------------------------------------------------------

class TestMaxPasses:
    def test_zero_passes_raises(self):
        with pytest.raises(ValidationError):
            PolicySpec(**make_policy(max_passes=0))

    def test_negative_passes_raises(self):
        with pytest.raises(ValidationError):
            PolicySpec(**make_policy(max_passes=-1))

    def test_one_pass_accepted(self):
        p = PolicySpec(**make_policy(max_passes=1))
        assert p.max_passes == 1


# ---------------------------------------------------------------------------
# 7. Refus cascade_enabled=false + cascade_target non nul
# ---------------------------------------------------------------------------

class TestCascadeTargetCoherence:
    def test_cascade_false_with_target_raises(self):
        with pytest.raises(ValidationError, match="cascade_target"):
            PolicySpec(**make_policy(cascade_enabled=False, cascade_target="some_model"))

    def test_cascade_false_with_null_target_accepted(self):
        p = PolicySpec(**make_policy(cascade_enabled=False, cascade_target=None))
        assert p.cascade_target is None


# ---------------------------------------------------------------------------
# 8. Refus cascade_enabled=true + cascade_target=null
# ---------------------------------------------------------------------------

    def test_cascade_true_with_null_target_raises(self):
        with pytest.raises(ValidationError, match="cascade_target"):
            PolicySpec(**make_policy(
                policy_id="cascade_x",
                execution_mode="cascade",
                cascade_enabled=True,
                cascade_target=None,
                max_passes=2,
            ))

    def test_cascade_true_with_target_accepted(self):
        p = PolicySpec(**make_policy(
            policy_id="cascade_x",
            execution_mode="cascade",
            cascade_enabled=True,
            cascade_target="large_model",
            max_passes=2,
        ))
        assert p.cascade_target == "large_model"


# ---------------------------------------------------------------------------
# 9. Refus verification_enabled=true + max_passes < 2
# ---------------------------------------------------------------------------

class TestVerificationPasses:
    def test_verify_true_one_pass_raises(self):
        with pytest.raises(ValidationError, match="max_passes"):
            PolicySpec(**make_policy(
                execution_mode="verify_pass",
                verification_enabled=True,
                max_passes=1,
            ))

    def test_verify_true_two_passes_accepted(self):
        p = PolicySpec(**make_policy(
            execution_mode="verify_pass",
            verification_enabled=True,
            max_passes=2,
        ))
        assert p.verification_enabled is True


# ---------------------------------------------------------------------------
# 10. get_policy
# ---------------------------------------------------------------------------

class TestGetPolicy:
    def test_get_existing_policy(self):
        registry = load_policy_registry(REGISTRY_JSON_PATH)
        p = get_policy(registry, "single_pass")
        assert p.policy_id == "single_pass"

    def test_get_missing_policy_raises(self):
        registry = load_policy_registry(REGISTRY_JSON_PATH)
        with pytest.raises(KeyError, match="absent du registre"):
            get_policy(registry, "nonexistent_policy")


# ---------------------------------------------------------------------------
# 11. Cohérences execution_mode
# ---------------------------------------------------------------------------

class TestExecutionModeCoherence:
    def test_single_pass_mode_requires_one_pass(self):
        with pytest.raises(ValidationError, match="max_passes"):
            PolicySpec(**make_policy(execution_mode="single_pass", max_passes=2))

    def test_verify_pass_mode_requires_min_two(self):
        with pytest.raises(ValidationError):
            PolicySpec(**make_policy(
                execution_mode="verify_pass",
                verification_enabled=True,
                max_passes=1,
            ))

    def test_cascade_mode_requires_cascade_enabled(self):
        with pytest.raises(ValidationError, match="cascade_enabled"):
            PolicySpec(**make_policy(
                policy_id="bad_cascade",
                execution_mode="cascade",
                cascade_enabled=False,
                cascade_target=None,
                max_passes=2,
            ))


# ---------------------------------------------------------------------------
# 12. list_policy_ids
# ---------------------------------------------------------------------------

class TestListPolicyIds:
    def test_returns_all_ids(self):
        registry = load_policy_registry(REGISTRY_JSON_PATH)
        ids = list_policy_ids(registry)
        assert len(ids) == 3
        assert ids == ["single_pass", "single_pass_verify", "cascade_small_to_large"]

    def test_returns_list_of_strings(self):
        registry = load_policy_registry(REGISTRY_JSON_PATH)
        ids = list_policy_ids(registry)
        assert all(isinstance(i, str) for i in ids)
