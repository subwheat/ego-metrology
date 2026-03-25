"""
ego_metrology.runners.run_benchmark
====================================
Runner canonique T5 — exécute task × policy × model -> RunRecord.

Flux nominal :
1. charger task + policy
2. vérifier que la policy est supportée
3. appeler le backend (ou dry_run)
4. construire RunRecord
5. calculer cost_dyn
6. append JSONL si demandé
7. retourner le record

Politiques supportées en exécution réelle :
    single_pass          → OK
    single_pass_verify   → NotImplementedError (dry_run accepté)
    cascade_small_to_large → NotImplementedError (dry_run accepté)
"""

from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from ego_metrology.backends.base import BackendResult, FakeBackend, GenerationBackend
from ego_metrology.benchmarks.bullshitbench import BenchmarkTask
from ego_metrology.cost import with_computed_cost_dyn
from ego_metrology.logging_schema import RunRecord, append_run_record_jsonl, make_run_record
from ego_metrology.policies import PolicyRegistry, PolicySpec, get_policy

# ---------------------------------------------------------------------------
# Politiques supportées en exécution réelle
# ---------------------------------------------------------------------------

EXECUTABLE_POLICIES = {"single_pass"}
DRYRUN_ONLY_POLICIES = {"single_pass_verify", "cascade_small_to_large"}


# ---------------------------------------------------------------------------
# RunRequest
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    """Contrat de requête d'exécution canonique."""

    task_id: str
    benchmark_id: str
    model_name: str
    policy_id: str
    backend_name: str
    manifest_hash: str
    calibration_status: str
    runner_version: str
    seed: Optional[int] = None
    output_jsonl_path: Optional[str] = None
    dry_run: bool = False


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _make_run_id() -> str:
    return str(uuid.uuid4()).upper().replace("-", "")[:26]


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _check_policy_executable(policy: PolicySpec, dry_run: bool) -> None:
    """Lève NotImplementedError si la policy n'est pas exécutable en mode réel."""
    if dry_run:
        return
    if policy.policy_id in DRYRUN_ONLY_POLICIES:
        raise NotImplementedError(
            f"La politique '{policy.policy_id}' n'est pas encore exécutable "
            f"en mode réel. Utilisez dry_run=True pour la tester."
        )
    if policy.policy_id not in EXECUTABLE_POLICIES:
        raise NotImplementedError(
            f"La politique '{policy.policy_id}' n'est pas reconnue "
            f"par le runner v1."
        )


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def run_task_with_policy(
    *,
    task: BenchmarkTask,
    model_name: str,
    policy_id: str,
    backend_name: str,
    manifest_hash: str,
    calibration_status: str,
    runner_version: str,
    registry: Optional[PolicyRegistry] = None,
    backend: Optional[GenerationBackend] = None,
    seed: Optional[int] = None,
    output_jsonl_path: Optional[str | Path] = None,
    dry_run: bool = False,
) -> RunRecord:
    """
    Exécute une tâche avec une politique donnée et retourne un RunRecord canonique.

    Args:
        task:                  BenchmarkTask normalisée.
        model_name:            Identifiant du modèle.
        policy_id:             Identifiant de la politique (doit exister dans registry).
        backend_name:          Nom du backend utilisé.
        manifest_hash:         Hash du CalibrationManifest.
        calibration_status:    experimental | candidate | frozen.
        runner_version:        Version du runner.
        registry:              PolicyRegistry chargé. Si None, politique non validée.
        backend:               Backend d'exécution. Obligatoire si dry_run=False.
        seed:                  Graine aléatoire optionnelle.
        output_jsonl_path:     Chemin JSONL append-only. Optionnel.
        dry_run:               Si True, pas d'appel backend réel.

    Returns:
        RunRecord canonique avec cost_dyn calculé si données disponibles.
    """
    # 1. Résoudre la policy
    if registry is not None:
        try:
            policy = get_policy(registry, policy_id)
        except KeyError:
            raise KeyError(f"policy_id '{policy_id}' absent du registry")
    else:
        # Sans registry, on crée un stub minimal pour la vérification
        from ego_metrology.policies import PolicySpec
        policy = PolicySpec(
            policy_id=policy_id,
            description="unvalidated",
            execution_mode="single_pass" if policy_id == "single_pass" else policy_id,
            verification_enabled=False,
            cascade_enabled=False,
            max_passes=1,
        )

    # 2. Vérifier exécutabilité
    _check_policy_executable(policy, dry_run)

    # 3. Appel backend
    backend_result: Optional[BackendResult] = None
    if not dry_run:
        if backend is None:
            raise ValueError(
                "dry_run=False mais aucun backend fourni. "
                "Fournissez un backend ou utilisez dry_run=True."
            )
        backend_result = backend.generate(
            prompt=task.prompt,
            model_name=model_name,
            policy_id=policy_id,
            seed=seed,
        )

    # 4. Construire meta
    meta = {
        **task.meta,
        "domain": task.domain,
        "technique": task.technique,
        "source_ref": task.source_ref,
        "benchmark_adapter": task.benchmark_id,
        "policy_execution_mode": policy.execution_mode,
        "dry_run": dry_run,
    }
    if backend_result is not None:
        if backend_result.response_text is not None:
            meta["response_text"] = backend_result.response_text
        if backend_result.backend_meta:
            meta["backend_meta"] = backend_result.backend_meta

    # 5. Construire RunRecord
    prompt_tokens = backend_result.prompt_tokens if backend_result else None
    completion_tokens = backend_result.completion_tokens if backend_result else None
    total_tokens = backend_result.total_tokens if backend_result else None

    latency_ms = backend_result.latency_ms if backend_result else None
    latency_total_ms = backend_result.latency_total_ms if backend_result else None

    provider_name = backend_result.provider_name if backend_result else None
    metrics_source = backend_result.metrics_source if backend_result else None

    prefill_ms = backend_result.prefill_ms if backend_result else None
    decode_ms = backend_result.decode_ms if backend_result else None
    queue_ms = backend_result.queue_ms if backend_result else None

    peak_vram_gb = backend_result.peak_vram_gb if backend_result else None
    gpu_power_w = backend_result.gpu_power_w if backend_result else None
    gpu_memory_used_mb = backend_result.gpu_memory_used_mb if backend_result else None
    gpu_utilization_pct = backend_result.gpu_utilization_pct if backend_result else None

    tools_count = backend_result.tools_count if backend_result else None
    loops_count = backend_result.loops_count if backend_result else None

    record = make_run_record(
        run_id=_make_run_id(),
        timestamp_utc=_now_utc(),
        task_id=task.task_id,
        benchmark_id=task.benchmark_id,
        model_name=model_name,
        policy_id=policy_id,
        backend_name=backend_name,
        manifest_hash=manifest_hash,
        calibration_status=calibration_status,
        runner_version=runner_version,
        seed=seed,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        latency_total_ms=latency_total_ms,
        provider_name=provider_name,
        metrics_source=metrics_source,
        prefill_ms=prefill_ms,
        decode_ms=decode_ms,
        queue_ms=queue_ms,
        peak_vram_gb=peak_vram_gb,
        gpu_power_w=gpu_power_w,
        gpu_memory_used_mb=gpu_memory_used_mb,
        gpu_utilization_pct=gpu_utilization_pct,
        tools_count=tools_count,
        loops_count=loops_count,
        meta=meta,
    )

    # 6. Calculer cost_dyn
    record = with_computed_cost_dyn(record)

    # 7. Append JSONL
    if output_jsonl_path is not None:
        path = Path(output_jsonl_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        append_run_record_jsonl(str(path), record)

    return record


def run_task_id_with_policy(
    *,
    task_id: str,
    tasks: list[BenchmarkTask],
    registry: PolicyRegistry,
    **kwargs,
) -> RunRecord:
    """
    Résout un task_id dans une liste de BenchmarkTask et exécute.

    Lève KeyError si le task_id est absent.
    """
    task_map = {t.task_id: t for t in tasks}
    if task_id not in task_map:
        raise KeyError(f"task_id '{task_id}' absent de la liste de tasks")
    return run_task_with_policy(task=task_map[task_id], registry=registry, **kwargs)


# ---------------------------------------------------------------------------
# CLI minimale
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="EGO Metrology — runner canonique T5"
    )
    p.add_argument("--tasks-path", required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--policy-id", required=True)
    p.add_argument("--model-name", required=True)
    p.add_argument("--backend-name", default="fake_backend")
    p.add_argument("--manifest-hash", default="dev-manifest")
    p.add_argument("--calibration-status", default="experimental")
    p.add_argument("--runner-version", default="ego-metrology/0.3.0-dev")
    p.add_argument("--output", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument(
        "--registry-path",
        default="ego_metrology/policy_registry.json",
    )
    return p


def main() -> None:
    from ego_metrology.benchmarks.bullshitbench import load_bullshitbench_tasks
    from ego_metrology.policies import load_policy_registry

    args = _build_parser().parse_args()

    tasks = load_bullshitbench_tasks(args.tasks_path)
    registry = load_policy_registry(args.registry_path)

    backend = FakeBackend() if args.backend_name == "fake_backend" else None

    record = run_task_id_with_policy(
        task_id=args.task_id,
        tasks=tasks,
        registry=registry,
        model_name=args.model_name,
        policy_id=args.policy_id,
        backend_name=args.backend_name,
        manifest_hash=args.manifest_hash,
        calibration_status=args.calibration_status,
        runner_version=args.runner_version,
        backend=backend,
        seed=args.seed,
        output_jsonl_path=args.output,
        dry_run=args.dry_run,
    )

    print(record.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
