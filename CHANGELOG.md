# Changelog

## v0.2.1 — 2026-03-18

### Added
- Full docstrings on `heuristics.py` module

### Changed
- Modernized packaging: `setuptools.build_meta`
- Added `dev` extras: `pytest`, `ruff`

---

## v0.2.0 — 2026-03-18

### Added
- `--json` output mode for CI/CD pipeline integration
- `calibration_status` field on all outputs (`heuristic` vs `calibrated`)
- 18 unit tests covering all core formulas and edge cases
- GitHub Actions CI on every push
- `heuristics.py` module — formulas and thresholds externalized and configurable

### Changed
- README repositioned: OSS is a heuristic context profiler, not a hallucination predictor
- Strict input validation — rejects negative, zero, float, and over-context values
- Heuristic presets clearly marked as uncalibrated

### Known limits
- Sectoral anchors (`a_secteur`, `beta_secteur`) are placeholder constants in OSS
- `τ` requires empirical calibration to be meaningful
- Public API remains intentionally narrow and heuristic-only

---

## v0.1.0 — 2026-03-18

### Added
- Initial release
- Core profiler: `α_S`, `r(η)`, `τ`
- CLI: `ego-profile <model> <tokens>` (also invokable via `python -m ego_metrology`)
- Four model presets: `mistral-7b`, `deepseek-14b`, `qwen-local`, `claude-api`
