# EGO Metrology

**Policy Metrology Core for LLMs**

> What is the cheapest inference policy that maintains acceptable quality on a given task?

## What this is

EGO Metrology is an open-source framework for **comparing LLM inference policies** under quality constraints.

It measures execution cost, computes an offline oracle of the optimal admissible policy, and quantifies the routing regret of any given policy choice.

## Core concepts

| Concept | Definition |
|---|---|
| `cost_dyn` | Canonical relative execution cost: `w_tokens × total_tokens + w_latency × latency_ms` |
| `C*` / `cost_star` | Minimum cost among policies that pass the quality threshold on a given task |
| `routing_regret` | `chosen_cost_dyn − cost_star` — how far a policy choice is from optimal |
| `oracle_policy_id` | The admissible policy with lowest cost, computed offline |
| `quality_pass_rate` | Proportion of runs where the policy meets the quality threshold |

## Architecture

```
Benchmark Layer       BullshitBench v2 (semantic pushback quality)
       ↓
Policy Registry       single_pass · single_pass_verify · cascade_small_to_large
       ↓
Runner (T5)           task × policy × model → RunRecord
       ↓
Oracle (T6)           C* = min cost_dyn among admissible runs per task
       ↓
Regret (T7)           routing_regret = chosen_cost − C*
       ↓
Reporting (T8)        policy comparison table · recommendation · CSV · Markdown
```

## Install

```bash
pip install ego-metrology
```

## Quickstart

```python
from ego_metrology.benchmarks.bullshitbench import load_bullshitbench_tasks
from ego_metrology.policies import load_policy_registry
from ego_metrology.backends.base import FakeBackend
from ego_metrology.runners.run_benchmark import run_task_with_policy
from ego_metrology.oracle import build_oracle_records
from ego_metrology.regret import build_regret_records
from ego_metrology.reporting import (
    build_policy_summary_records,
    summarize_sprint_outcome,
    render_markdown_report,
)

# Load tasks and policy registry
tasks = load_bullshitbench_tasks("tests/fixtures/bullshitbench_sample_tasks.json")
registry = load_policy_registry("ego_metrology/policy_registry.json")

# Run a task with a policy
record = run_task_with_policy(
    task=tasks[0],
    model_name="qwen2.5-14b",
    policy_id="single_pass",
    backend_name="local_vllm",
    manifest_hash="sha256:...",
    calibration_status="experimental",
    runner_version="ego-metrology/0.3.0",
    backend=FakeBackend(),
    output_jsonl_path="runs/sample.jsonl",
)

# Compute oracle and regret from a set of runs
oracle_records = build_oracle_records(runs)
regret_records = build_regret_records(runs, oracle_records)

# Generate a sprint report
summaries = build_policy_summary_records(runs, regret_records)
sprint = summarize_sprint_outcome(summaries)
report = render_markdown_report(summaries, sprint, benchmark_id="bullshitbench_v2")
```

## Core modules

| Module | Role |
|---|---|
| `ego_metrology/logging_schema.py` | `RunRecord` — canonical unit of measurement |
| `ego_metrology/policies.py` | `PolicyRegistry` — declarative policy registry |
| `ego_metrology/cost.py` | `cost_dyn` v1 computation |
| `ego_metrology/benchmarks/bullshitbench.py` | BullshitBench v2 adapter |
| `ego_metrology/backends/base.py` | Backend protocol + `FakeBackend` |
| `ego_metrology/runners/run_benchmark.py` | Canonical benchmark runner |
| `ego_metrology/oracle.py` | Offline oracle `C*` |
| `ego_metrology/regret.py` | `routing_regret` computation |
| `ego_metrology/reporting.py` | Sprint report — Markdown + CSV |

## Policy registry

Three policies are defined in v1:

| `policy_id` | Description | Executable |
|---|---|---|
| `single_pass` | Single generation, no verification | ✅ |
| `single_pass_verify` | Generation + explicit verification pass | dry-run only |
| `cascade_small_to_large` | Escalate to stronger model if needed | dry-run only |

## BullshitBench integration

EGO Metrology uses [BullshitBench](https://github.com/ErikBjare/bullshitbench) as its first external quality benchmark.

BullshitBench measures whether a model correctly **resists an absurd premise** instead of engaging with it.

EGO adds the cost dimension:

- BullshitBench says **if** the response is semantically correct
- EGO measures **at what cost**, **with which policy**, and **whether that cost was minimal**

Score mapping:

| BullshitBench score | Meaning | `passed_quality` |
|---|---|---|
| 0 | Full engagement with absurdity | False |
| 1 | Partial recognition | False |
| 2 | Clear pushback | True |

`quality_threshold = 2.0`

## CLI

```bash
# Run a single task (fake backend)
python -m ego_metrology.runners.run_benchmark \
  --tasks-path tests/fixtures/bullshitbench_sample_tasks.json \
  --task-id bullshitbench_v2_software_0001 \
  --policy-id single_pass \
  --model-name qwen2.5-14b \
  --backend-name fake_backend \
  --output runs/sample.jsonl

# Legacy heuristic profiler (v0.2 API, still available)
ego-profile deepseek-14b 12000
```

## API server

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

Endpoints: `GET /health` · `GET /models` · `POST /profile`

## Run tests

```bash
pip install -e ".[dev]"
pytest -q
```

## What v0.3 does not yet do

- Real LLM backend calls (use `FakeBackend` or bring your own backend)
- `single_pass_verify` and `cascade_small_to_large` in real execution mode
- API endpoints for oracle and regret (`/v1/oracle`, `/v1/run`)
- Multi-benchmark comparison
- Dashboard or visualizations

## License

MIT — © 2026 Julien Tournier / Uyuni
