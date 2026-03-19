#!/usr/bin/env python3
"""Run this from ~/ego-metrology: python3 patch_changelog2.py"""
import subprocess, sys
from pathlib import Path

p = Path("CHANGELOG.md")
text = p.read_text()

# ── Patch 1 : v0.2.0 Known limits ───────────────────────────────────────────

old1 = """### Known limits
- Sectoral anchors (`a_secteur`, `beta_secteur`) are placeholder constants in OSS
- `τ` requires empirical calibration to be meaningful
- No FastAPI server yet (coming in v0.3)"""

new1 = """### Known limits
- Sectoral anchors (`a_secteur`, `beta_secteur`) are placeholder constants in OSS
- `τ` requires empirical calibration to be meaningful
- Public API remains intentionally narrow and heuristic-only"""

if old1 not in text:
    print("[ERR] bloc Known limits v0.2.0 non trouvé")
    sys.exit(1)

text = text.replace(old1, new1, 1)
print("→ patch 1 OK (v0.2.0 Known limits)")

# ── Patch 2 : v0.1.0 CLI line ────────────────────────────────────────────────

old2 = "- CLI: `ego-profile <model> <tokens>`"
new2 = "- CLI: `ego-profile <model> <tokens>` (also invokable via `python -m ego_metrology`)"

if old2 not in text:
    print("[ERR] ligne CLI v0.1.0 non trouvée")
    sys.exit(1)

text = text.replace(old2, new2, 1)
print("→ patch 2 OK (v0.1.0 CLI)")

# ── Écriture ──────────────────────────────────────────────────────────────────

p.write_text(text)
print("→ CHANGELOG.md écrit")

# ── Vérification rapide ───────────────────────────────────────────────────────

print("\n===== CHANGELOG HEAD =====")
print("\n".join(p.read_text().splitlines()[:60]))

print("\n===== TESTS =====")
result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "-W", "error::DeprecationWarning"],
    capture_output=False
)
sys.exit(result.returncode)
