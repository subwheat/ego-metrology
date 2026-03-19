#!/usr/bin/env python3
"""Run this from ~/ego-metrology: python3 patch_changelog.py"""
import subprocess, sys
from pathlib import Path

p = Path("CHANGELOG.md")
text = p.read_text()

old = """### Changed
- README repositioned: OSS is a heuristic context profiler, not a hallucination predictor
- Strict input validation — rejects negative, zero, float, and over-context values
- Heuristic presets clearly marked as uncalibrated
### Known limits
- Sectoral anchors (`a_secteur`, `beta_secteur`) are placeholder constants in OSS
- `τ` requires empirical calibration to be meaningful
- No FastAPI server yet (coming in v0.3)
"""

new = """### Changed
- README repositioned: OSS is a heuristic context profiler, not a hallucination predictor
- Strict input validation — rejects negative, zero, float, and over-context values
- Heuristic presets clearly marked as uncalibrated
- Minimal FastAPI server exposed with `/health`, `/models`, `/profile`
### Known limits
- Sectoral anchors (`a_secteur`, `beta_secteur`) are placeholder constants in OSS
- `τ` requires empirical calibration to be meaningful
- Public API remains intentionally narrow and heuristic-only
"""

if old not in text:
    print("[ERR] bloc attendu non trouvé dans CHANGELOG.md")
    print("\n--- Contenu actuel du CHANGELOG ---")
    print(text[:2000])
    sys.exit(1)

p.write_text(text.replace(old, new, 1))
print("→ CHANGELOG.md patché")

print("\n===== CHANGELOG HEAD =====")
lines = p.read_text().splitlines()
print("\n".join(lines[:120]))

print("\n===== TESTS =====")
result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "-W", "error::DeprecationWarning"],
    capture_output=False
)
sys.exit(result.returncode)
