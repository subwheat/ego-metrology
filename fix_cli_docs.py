#!/usr/bin/env python3
"""Run this from ~/ego-metrology: python3 fix_cli_docs.py"""
import subprocess, sys
from pathlib import Path

# ── README ──────────────────────────────────────────────────────────────────

readme = Path("README.md")
text = readme.read_text()

old_cli = """## CLI
```bash
python -m ego_metrology deepseek-14b 12000
python -m ego_metrology deepseek-14b 12000 --json
python -m ego_metrology --list
```"""

new_cli = """## CLI
**Preferred (after `pip install ego-metrology`):**
```bash
ego-profile deepseek-14b 12000
ego-profile deepseek-14b 12000 --json
ego-profile --list
```
**Alternative (clone without install):**
```bash
python -m ego_metrology deepseek-14b 12000
python -m ego_metrology deepseek-14b 12000 --json
python -m ego_metrology --list
```"""

if old_cli not in text:
    print("[ERR] bloc CLI attendu non trouvé dans README.md")
    print("--- extrait README actuel ---")
    print(text[:3000])
    sys.exit(1)

readme.write_text(text.replace(old_cli, new_cli, 1))
print("→ README.md patché (section CLI)")

# ── CHANGELOG ───────────────────────────────────────────────────────────────

changelog = Path("CHANGELOG.md")
text = changelog.read_text()

old_cl = "- Initial CLI for model/token profiling"
new_cl = "- Initial CLI for model/token profiling (`ego-profile`, also invokable via `python -m ego_metrology`)"

if old_cl not in text:
    print("[WARN] ligne CHANGELOG attendue non trouvée — vérification manuelle requise")
else:
    changelog.write_text(text.replace(old_cl, new_cl, 1))
    print("→ CHANGELOG.md patché")

# ── TESTS ────────────────────────────────────────────────────────────────────

print("\n===== TESTS =====")
result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "-W", "error::DeprecationWarning"],
    capture_output=False
)
sys.exit(result.returncode)
