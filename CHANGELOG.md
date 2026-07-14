# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] - 2026-07-14

### Added
- Adaptive performance regression testing for benchmarks: metrics from historical
  runs (stored in S3 Parquet) are used to compute statistical baselines and detect
  regressions automatically.
- New `compute_baselines()` function using median + MAD (k=3.5, scaled
  MAD with an explicit minimum absolute decision band: `max(2.0, k * scaled_MAD)`)
  for robust threshold computation.
- New `check_reference_performance()` function to compare tracked metrics against
  computed baselines.
- New `metrics.parquet_metrics` module (`load_scenario_metrics`,
  `load_recent_scenario_metrics_map`) for loading per-scenario metric history
  from Parquet on S3.
- `max_age_days` parameter in history loading helpers to discard stale
  historical runs.
- `github_issue_handler` now includes `ScenarioRunInfo` and
  `PerformanceRegressionInfo` for formatting benchmark and regression issue markdown.
- `PerformanceRegressionInfo` now includes scenario metadata (definition
  link, backend, contacts) and presents a cost-trend table rather than mirroring
  the test-failure format.
- `PerformanceRegressionInfo` now accepts an optional `BenchmarkScenario` to
  enrich regression issues with scenario definition links and contact information.
- Weekly `performance-analysis.yml` workflow that reads S3 Parquet history and
  opens or updates GitHub issues for detected cost regressions.


### Fixed
