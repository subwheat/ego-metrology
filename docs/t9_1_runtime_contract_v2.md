# T9.1 — Runtime Contract v2 (cross-LLM compatible)

## Goal

Freeze a canonical runtime contract that allows clean comparison of executions across:

- local LLMs
- remote OpenAI-compatible backends
- provider APIs (Anthropic, OpenAI, etc.)

without breaking:

- `runrecord.v1`
- `cost_dyn v1`
- offline oracle `C*`
- routing regret
- T8 strictly policy-aware reporting
- the legacy `/profile` API

---

## Design principles

1. Keep a **portable minimal core** shared by all backends.
2. Allow **optional fine-grained metrics** for local LLMs / instrumented infrastructure.
3. Preserve **backward compatibility** with the existing v1 contract.
4. Do not mix:
   - existing **policy-aware** reporting
   - future **model-aware** reporting
5. Do not replace `cost_dyn v1` immediately.

---

## Scope

This document defines:

- the target contract for `BackendResult`
- the target contract for `RunRecord`
- the v1/v2 compatibility strategy
- the separation between current cost and future cost
- the separation between policy-aware and model-aware reporting

This document does **not** define yet:

- a new canonical cross-LLM cost
- a server API redesign
- a dashboard
- mandatory GPU instrumentation
- ACP semantics

---

## 1. Portable minimal cross-LLM core

The following fields define the **canonical portable core** that should be surfaced whenever available:

- `provider_name`
- `metrics_source`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `latency_total_ms`

### Field intent

#### `provider_name`

Logical name of the source provider or backend.

Examples:

- `openai_compat`
- `anthropic`
- `openai`
- `local_vllm`
- `ollama`

#### `metrics_source`

Origin and trust level of the runtime metrics.

Proposed enum:

- `observed_local`
- `provider_reported`
- `derived`
- `none`

#### `prompt_tokens`

Number of input tokens.

#### `completion_tokens`

Number of output tokens.

#### `total_tokens`

Canonical sum:

```text
total_tokens = prompt_tokens + completion_tokens
```

when both values are known.

#### `latency_total_ms`

Observable total latency for the full call.

This is the minimal portable latency measure across all backends.

---

## 2. Optional fine-grained metrics

These metrics are **optional** and primarily intended for local LLMs or truly instrumented environments.

- `prefill_ms`
- `decode_ms`
- `queue_ms`
- `peak_vram_gb`
- `gpu_power_w`
- `gpu_memory_used_mb`
- `gpu_utilization_pct`
- `tools_count`
- `loops_count`

### Interpretation

#### `prefill_ms`

Estimated or observed time spent on prefill / context ingestion.

#### `decode_ms`

Estimated or observed time spent on generation.

#### `queue_ms`

Time spent waiting before actual execution starts.

#### `peak_vram_gb`

Peak GPU memory usage during the run, in GB.

#### `gpu_power_w`

Observed or aggregated GPU power draw during the run.

#### `gpu_memory_used_mb`

GPU memory used, in MB.

#### `gpu_utilization_pct`

Average or representative GPU utilization.

#### `tools_count`

Number of tool calls performed by the policy or agent.

#### `loops_count`

Number of agentic loops / iterations performed.

---

## 3. v1 → v2 compatibility rules

The current repository still relies on `latency_ms` and on a minimally enriched v1 `RunRecord`.

The v2 contract must therefore respect the following rules.

### 3.1 `latency_ms` remains accepted

The historical `latency_ms` field remains supported.

### 3.2 Controlled duplication of total latency

If only a wall-clock total latency is known, then:

- `latency_ms` is populated
- `latency_total_ms` is also populated with the same value

### 3.3 v2 fields are optional

All new runtime v2 fields are **optional**.

Missing measurements must not invalidate a run.

### 3.4 No JSONL breakage

Loading old JSONL files must continue to work without destructive migration.

### 3.5 No breakage of business invariants

The invariants used by:

- offline oracle
- regret
- policy-aware reporting

must remain valid without requiring the new v2 fields.

---

## 4. Target contract for `BackendResult`

`BackendResult` must evolve toward a v2-compatible contract while keeping the existing fields.

### Historical fields to keep

- `response_text`
- `prompt_tokens`
- `completion_tokens`
- `latency_ms`
- `backend_meta`

### v2 fields to add

- `provider_name`
- `metrics_source`
- `latency_total_ms`
- `prefill_ms`
- `decode_ms`
- `queue_ms`
- `peak_vram_gb`
- `gpu_power_w`
- `gpu_memory_used_mb`
- `gpu_utilization_pct`
- `tools_count`
- `loops_count`

### Rule

A minimal backend must be allowed to populate only:

- `response_text`
- `prompt_tokens`
- `completion_tokens`
- `latency_ms` or `latency_total_ms`

while remaining valid.

---

## 5. Target contract for `RunRecord`

`RunRecord` must be able to carry enriched runtime information without breaking the existing core.

### Target runtime fields

- `provider_name`
- `metrics_source`
- `latency_total_ms`
- `prefill_ms`
- `decode_ms`
- `queue_ms`
- `peak_vram_gb`
- `gpu_power_w`
- `gpu_memory_used_mb`
- `gpu_utilization_pct`
- `tools_count`
- `loops_count`

### Constraints

- `make_run_record()` must continue to work
- R2/R3 validations remain unchanged
- JSONL append/load remains unchanged
- legacy runs remain readable

---

## 6. Runner propagation rule

The canonical runner must stop discarding available runtime information.

### Expected mapping

The `BackendResult -> RunRecord` mapping must:

- copy all known v2 fields
- preserve `latency_ms`
- populate `latency_total_ms` when only total wall-clock latency is known
- leave unavailable metrics as `None`

### Objective

Enable richer future comparisons without breaking the current pipeline.

---

## 7. Cost policy

### Current state preserved

As long as the repository remains on the v1 cost model:

```text
cost_dyn v1 = total_tokens + 0.001 * latency_ms
```

remains the canonical existing reference.

### Decision

We do **not** replace `cost_dyn v1` in this ticket.

### Planned follow-up

A future `cost_dyn_v2` may use, when available:

- `latency_total_ms`
- `prefill_ms`
- `decode_ms`
- `queue_ms`
- `tools_count`
- `loops_count`
- GPU metrics

but through a separate explicit path.

---

## 8. Reporting policy

### T8 must remain unchanged

The current reporting layer is strictly **policy-aware**.

It groups by:

- `policy_id`

This semantics must not change during the runtime v2 transition.

### Planned follow-up

A separate **model-aware** reporting layer will be added later, for example using:

- `model_name`
- or `(model_name, policy_id)`

without modifying `PolicySummaryRecord` or the existing T8 outputs.

---

## 9. Security and trust of metrics

Not all runtime metrics have the same status.

### Practical hierarchy

#### `observed_local`

Locally instrumented measurement.
Highest trust from the observer system.

#### `provider_reported`

Metric reported by an external provider.
Usable, but dependent on provider behavior.

#### `derived`

Value reconstructed or computed from other signals.
Must be interpreted as an approximation.

#### `none`

No reliable provenance available.

### Rule

The system must carry metric provenance, not just raw values.

---

## 10. Immediate non-goals

Do not do the following in this phase:

- full server refactor
- replacement of `/profile`
- presenting cross-LLM cost as scientifically stabilized
- fake GPU instrumentation
- merging policy-aware and model-aware reporting
- mandatory dependence on local metrics unavailable from provider APIs

---

## 11. Acceptance criteria for T9.1

The ticket is considered complete if:

1. the portable minimal core is defined explicitly
2. the optional fine-grained metrics are listed
3. v1/v2 compatibility is made explicit
4. the separation between `cost_dyn v1` and future `cost_dyn_v2` is documented
5. the separation between policy-aware and model-aware reporting is documented
6. the document does not break any existing core assumption

---

## 12. Consequence for the next tickets

After this spec is validated, the recommended order is:

1. extend `BackendResult`
2. extend `RunRecord`
3. propagate metrics through the canonical runner
4. add runtime v2 tests
5. secure SSL behavior in the Anthropic backend
6. add separate model-aware reporting
7. add `cost_dyn_v2`

---

## 13. Executable summary

The selected trajectory is:

```text
portable runtime contract v2
-> canonical propagation of metrics
-> full compatibility with the v1 core
-> separate model-aware reporting later
-> cost_dyn_v2 later
```
