#!/usr/bin/env python3
"""Run this from ~/ego-metrology: python3 write_readme.py"""
import subprocess, sys
from pathlib import Path

README = """\
# EGO Metrology
**Heuristic Context Saturation Profiler for LLMs**
> Know when your context is working against you — before you generate a single token.

## What this is
EGO Metrology is an **open-source heuristic profiler**. It estimates context
saturation and structural load for LLM prompts, based on the EGO V12.2
theoretical framework (Holographic Quantum Error Correction / Tensor Networks).

## What OSS does
- Measures **context pressure** `η` — how full your window really is
- Estimates **spectatorization ratio** `α_S` — passive overhead vs active computation
- Flags **geometric saturation** `r(η)` — the point where adding tokens stops helping
- Provides an **uncalibrated** logical decay estimate `τ`
- Exposes a minimal FastAPI surface for remote profiling

## What OSS does not do
- Does not measure model internals (logits, attention, entropy)
- Does not predict hallucination probability
- Does not provide calibrated `τ` values — empirical sectoral anchors are Enterprise only
- Does not yet expose replayable calibration runs or policy-regret evaluation in the public API

## Install
```bash
pip install ego-metrology
```

## Quickstart
```python
from ego_metrology import EgoProfiler
profiler = EgoProfiler("deepseek-14b")
result = profiler.profile(prompt_tokens=12_000)
print(result)
# or:
print(result.model_dump() if hasattr(result, "model_dump") else result.dict())
```

## The Three Metrics

**1. Spectatorization Ratio — `α_S`**
Heuristic estimate of passive context overhead.
`α_S → 1` means your prompt is bearing heavy structural weight.

**2. Geometric Saturation — `r(η)`**
Position on the continuum between linear attention (`r = 1.2071`)
and holographic saturation (`r = π/2 ≈ 1.5708`).
Past the bound, adding tokens yields diminishing returns.

**3. Logical Decay Estimate — `τ`** *(uncalibrated in OSS)*
A structural estimate of output coherence lifespan.
Requires empirically validated sectoral anchors to be meaningful.
Calibrated values are not part of the public OSS package.

## CLI
```bash
python -m ego_metrology deepseek-14b 12000
python -m ego_metrology deepseek-14b 12000 --json
python -m ego_metrology --list
```

## Theoretical Background
Based on the **EGO V12.2 framework**, applying principles from:
* Holographic Quantum Error Correction (HQEC)
* Holographic Tensor Networks
* Dissipative thermodynamics for logical coherence decay

These remain **structuring metaphors / heuristics** in OSS, not claims about direct measurement of model internals.

## API Server
A minimal FastAPI server is included for remote profiling.

**Launch locally:**
```bash
pip install fastapi uvicorn
uvicorn server:app --host 0.0.0.0 --port 8000
```

**Endpoints:**
* `GET /health` — liveness probe
* `GET /models` — list available model presets
* `POST /profile` — run heuristic EGO profiling

**Interactive docs:** `http://127.0.0.1:8000/docs`

### Example request
```bash
curl -s http://127.0.0.1:8000/profile \\
  -H 'Content-Type: application/json' \\
  -d '{"model_name":"mistral-7b","prompt_tokens":1200}'
```

## EGO Enterprise
The open-core library provides the heuristic measurement framework.
A separate enterprise layer may add empirical calibration, historical tracking,
and broader production tooling.

## License
MIT — © 2026 Julien Tournier / Uyuni
"""

target = Path("README.md")
target.write_text(README, encoding="utf-8")
print(f"✅ README.md written ({len(README)} chars)")

result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "-W", "error::DeprecationWarning"],
    capture_output=False
)
sys.exit(result.returncode)
