# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Backwards-compatible algorithm discovery with case-insensitive provider,
  platform, and keyword filters, plus `details=True` for parsed `Algorithm`
  results. For example:
  `repo.list_algorithms(provider="VITO", keywords=["Climate"], details=True)`.
- `Algorithm.provider`, `Algorithm.platforms`, and `Algorithm.keywords`, with
  safe defaults for missing discovery metadata.
- `list_providers()`, `list_platforms()`, and `list_keywords()` discovery helpers.
- Parallel raw record downloads and per-instance caching shared with
  `get_algorithm()`; directory listings now honor the configured branch.

### Fixed
- Ignore non-UDP application links (such as CWL packages) when parsing UDP
  metadata, allowing detailed discovery across the complete catalog.

## [released] - 2026-07-14

### Added
- Adaptive performance regression testing for benchmarks: metrics from historical
  runs (stored in S3 Parquet) are used to compute statistical baselines and detect
  regressions automatically.
- New `_compute_baselines()` function using median + MAD (k=3.0, scaled
  MAD with an explicit minimum absolute margin: `max(min_margin, k * scaled_MAD)`)
  for robust threshold computation.
- New `_check_reference_performance()` function to compare tracked metrics against
  computed baselines using `upper_limit` and `lower_limit` keys.
- New `metrics.parquet_metrics` module (`load_scenario_metrics`,
  `load_recent_scenario_metrics_map`) for loading per-scenario metric history
  from Parquet on S3 with optimized column projection and filter pushdown.
- `max_age_days` parameter in history loading helpers to discard stale
  historical runs.
- `github_issue_handler` now includes `ScenarioRunInfo` and
  `PerformanceRegressionInfo` for formatting benchmark and regression issue markdown.
- `PerformanceRegressionInfo` now includes scenario metadata (definition
  link, backend, contacts) and presents a cost-trend table with mermaid charts.
- `PerformanceRegressionInfo` now accepts an optional `BenchmarkScenario` to
  enrich regression issues with scenario definition links and contact information.
- Weekly `regression-testing.yml` workflow that reads S3 Parquet history and
  opens or updates GitHub issues for detected cost regressions.
- Unit tests for regression metrics in `test_regression_metrics.py` covering
  threshold computation, baseline computation, violation detection, and issue body rendering.

### Fixed
