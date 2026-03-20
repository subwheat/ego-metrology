# Changelog

## v0.3.0 — 2026-03-20

### Added — Policy Metrology Core

**T1 — Canonical RunRecord schema**
- `ego_metrology/logging_schema.py` — `RunRecord` Pydantic model, append-only JSONL I/O
- Schema version `runrecord.v1` with cross-field validators (R2 total_tokens, R3 passed_quality)
- `make_run_record()`, `append_run_record_jsonl()`, `load_run_records_jsonl()`

**T2 — Policy registry**
- `ego_metrology/policy_registry.json` — declarative registry, schema version `policy-registry.v1`
- `ego_metrology/policies.py` — `PolicySpec`, `PolicyRegistry`, cross-field coherence validators
- Three initial policies: `single_pass`, `single_pass_verify`, `cascade_small_to_large`

**T3 — cost_dyn v1**
- `ego_metrology/cost.py` — `cost_dyn = w_tokens × total_tokens + w_latency × latency_ms`
- Schema version `cost-dyn.v1`, weights `w_tokens=1.0`, `w_latency=0.001`
- `compute_cost_dyn()`, `compute_cost_dyn_from_run()`, `with_computed_cost_dyn()`

**T4 — BullshitBench adapter**
- `ego_metrology/benchmarks/bullshitbench.py` — BullshitBench v2 adapter
- `BenchmarkTask`, `BenchmarkJudgment` models
- Score mapping: `0→fail`, `1→fail`, `2→pass`, `quality_threshold=2.0`
- `load_bullshitbench_tasks()`, `load_bullshitbench_judgments()`, `map_bullshitbench_score()`
- `make_run_record_from_bullshitbench_task()`, `merge_bullshitbench_judgment_into_run()`
- Test fixtures: `tests/fixtures/bullshitbench_sample_tasks.json` (5 items, 4 domains)

**T5 — Canonical benchmark runner**
- `ego_metrology/runners/run_benchmark.py` — `task × policy × model → RunRecord`
- `ego_metrology/backends/base.py` — `GenerationBackend` protocol + `FakeBackend`
- `single_pass` executable; `single_pass_verify` and `cascade_small_to_large` dry-run only
- JSONL append-only output, auto-creates parent directories
- CLI: `python -m ego_metrology.runners.run_benchmark`

**T6 — Offline oracle C***
- `ego_metrology/oracle.py` — `OracleRecord`, schema version `oracle.v1`
- `C*(task) = min cost_dyn` over admissible runs (`passed_quality=True`, `cost_dyn≠None`)
- Tie-break: cost asc → quality_score desc → policy_id lexicographic
- `select_oracle_run_for_task()`, `build_oracle_records()`, `summarize_oracle_records()`
- Selection statuses: `ok`, `no_admissible_run`

**T7 — routing_regret**
- `ego_metrology/regret.py` — `RegretRecord`, schema version `routing-regret.v1`
- `routing_regret = chosen_cost_dyn − cost_star`
- Regret statuses: `ok`, `no_oracle`, `chosen_cost_missing`, `benchmark_mismatch`
- Negative regrets preserved and flagged in `meta`
- `make_regret_record()`, `build_regret_records()`, `summarize_regret_records()`

**T8 — Sprint reporting**
- `ego_metrology/reporting.py` — `PolicySummaryRecord`, schema version `reporting.v1`
- Aggregates `quality_pass_rate`, `mean_cost_dyn`, `mean_routing_regret`, `oracle_match_rate` per policy
- Default policy recommendation rule: pass rate → regret → cost → lexicographic
- `render_markdown_report()`, `write_policy_summary_csv()`

### Changed
- `pyproject.toml` — version bumped to `0.3.0`
- `pyproject.toml` — runtime dependency `pydantic>=2.0` declared
- `pyproject.toml` — `policy_registry.json` included in package data
- `pyproject.toml` — description and keywords updated
- README rewritten around the policy metrology core

### Test coverage
- 253 tests passing across T1–T8
- Covers schema validation, cross-field coherence, JSONL I/O, oracle selection,
  tie-break stability, regret computation, policy recommendation

### Known limits
- `single_pass_verify` and `cascade_small_to_large` not yet executable in real mode
- `cost_dyn` v1 is a token+latency proxy, not a real provider cost
- No API endpoints for oracle/regret yet (`/v1/oracle`, `/v1/run` planned)
- BullshitBench integration uses local fixtures only — no live dataset download

---

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
