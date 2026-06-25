# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).


### Added
- Adaptive performance regression testing for benchmarks: metrics from historical
  runs (stored in S3 Parquet) are used to compute statistical baselines and detect
  regressions automatically.
- New `compute_baselines()` function using median + MAD (k=3.5, scaled
  MAD with floor of 1.0) for robust threshold computation.
- New `check_reference_performance()` function to compare tracked metrics against
  computed baselines.
- New `benchmark_history` module (`load_scenario_history`, `create_s3_filesystem`)
  for loading per-scenario metric history from Parquet on S3.
- `max_age_days` parameter in `load_scenario_history` to discard stale historical runs.
- `github_issue_handler` now includes `ScenarioRunInfo` and
  `PerformanceRegressionInfo` for formatting benchmark and regression issue markdown.
- `PerformanceRegressionInfo` now includes scenario metadata (definition
  link, backend, contacts) and presents a cost-trend table rather than mirroring
  the test-failure format.
- `PerformanceRegressionInfo` now accepts an optional `BenchmarkScenario` to
  enrich regression issues with scenario definition links and contact information.
- Weekly `performance-analysis.yml` workflow that reads S3 Parquet history and
  opens or updates GitHub issues for detected cost regressions.

### Changed
- Performance regression logic (`compute_baselines`,
  `check_reference_performance`) was moved to a dedicated
  `benchmark_regression` module.
- GitHub issue handling stays consolidated in `github_issue_handler` while keeping
  TODO markers for future extraction of API, parser, and formatting pieces.
- `report_performance_regressions.py` now delegates all GitHub issue formatting
  to `PerformanceRegressionInfo` instead of building issue bodies inline.
- Unit tests were updated to match the current benchmark API naming
  (`compute_baselines`) and current GitHub issue handler structure.

### Fixed
