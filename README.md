# EGO Metrology

**Heuristic Context Saturation Profiler for LLMs**

> Know when your context is working against you — before you generate a single token.

## What this is

EGO Metrology is an **open-source heuristic profiler**. It estimates context
saturation and structural load for LLM prompts, based on the EGO V12.2
theoretical framework (Holographic Quantum Error Correction / Tensor Networks).

## What OSS does

- Measures **context pressure** η — how full your window really is
- Estimates **spectatorization ratio** α_S — passive overhead vs active computation
- Flags **geometric saturation** r(η) — the point where adding tokens stops helping
- Provides an **uncalibrated** logical decay estimate τ

## What OSS does not do

- Does not measure model internals (logits, attention, entropy)
- Does not predict hallucination probability
- Does not provide calibrated τ values — empirical sectoral anchors are Enterprise only

## Install
```bash
pip install ego-metrology
```

## Quickstart
```python
from ego_metrology import EgoProfiler

profiler = EgoProfiler("deepseek-14b")
result   = profiler.profile(prompt_tokens=12_000)
print(result.summary())
```

## The Three Metrics

**1. Spectatorization Ratio — α_S**
Heuristic estimate of passive context overhead.
`α_S → 1` means your prompt is bearing heavy structural weight.

**2. Geometric Saturation — r(η)**
Position on the continuum between linear attention (r=1.2071)
and holographic saturation (r=π/2 ≈ 1.5708).
Past the bound, adding tokens yields diminishing returns.

**3. Logical Decay Estimate — τ** *(uncalibrated in OSS)*
A structural estimate of output coherence lifespan.
Requires empirically validated sectoral anchors to be meaningful.
Calibrated values are available in EGO Enterprise.

## CLI
```bash
ego-profile deepseek-14b 12000
ego-profile --list
```

## Theoretical Background

Based on the **EGO V12.2 framework**, applying principles from:
- Holographic Quantum Error Correction (HQEC)
- Holographic Tensor Networks (Evenbly)
- Dissipative thermodynamics for logical coherence decay

## EGO Enterprise

The open-core library provides the heuristic measurement framework.
**EGO Enterprise** adds empirical calibration and production tooling:

- Validated sectoral anchors for GPT-4, Claude, Gemini, Mistral
- Full bulk/boundary recoverability testing
- Visual dashboard + historical tracking
- CI/CD integration

→ julien@uyuni.world

## License

MIT — © 2026 Julien Tournier / Uyuni
