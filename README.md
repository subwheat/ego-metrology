# EGO Metrology

**Thermodynamic & Holographic Profiling for LLMs**

> Stop guessing when your LLM will hallucinate. Measure its structural limits.

Modern LLMs ingest massive contexts — 50k, 100k, 200k tokens — but performance
degrades unpredictably. EGO Metrology introduces three physics-derived metrics,
based on the **EGO V12.2 framework**, to profile any prompt before generation.

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
How much of your context becomes passive overhead vs active computation.
`α_S → 1` means the model is bearing the full structural weight of the context.

**2. Geometric Saturation — r(η)**
Where your prompt sits on the continuum between linear attention (r=1.2071)
and holographic saturation (r=π/2 ≈ 1.5708). Past the bound, adding tokens is futile.

**3. Logical Decay Estimator — τ**
Predicted number of coherent output tokens before hallucination onset.
Requires calibrated sectoral anchors — available in EGO Enterprise.

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

The open-core library provides the measurement framework.
**EGO Enterprise** adds what actually makes it production-ready:

- Empirically calibrated sectoral anchors for GPT-4, Claude, Gemini, Mistral
- Full bulk/boundary recoverability testing
- Visual dashboard + historical tracking
- CI/CD integration

→ julien@uyuni.world

## License

MIT — © 2026 Julien Tournier / Uyuni
