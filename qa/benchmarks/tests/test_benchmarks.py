import json
import logging
import re
from pathlib import Path

import pytest
from apex_algorithm_qa_tools.scenarios import (
    BenchmarkScenario,
    download_reference_data,
    get_benchmark_scenarios,
)
from openeo.testing.results import assert_job_results_allclose

from apex_algorithm_qa_tools.benchmarks.runners.factory import (
    create_benchmark_runner
)

from apex_algorithm_qa_tools.benchmarks.common import (
    analyse_results_comparison_exception, 
    collect_metrics_from_job_metadata, 
    collect_metrics_from_results_metadata
)

_log = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "scenario",
    [
        # Use scenario id as parameterization id to give nicer test names.
        pytest.param(uc, id=uc.id)
        for uc in get_benchmark_scenarios()
    ],
)
def test_run_benchmark(
    scenario: BenchmarkScenario,
    tmp_path: Path,
    track_metric,
    track_phase,
    upload_assets_on_fail,
    request,
):
    track_metric("scenario_id", scenario.id)
    track_metric("scenario_type", scenario.type)

    with track_phase(phase="connect"):
        runner = create_benchmark_runner(
            request=request,
            scenario=scenario,
        )

    report_path = None
    if request.config.getoption("--upload-benchmark-report"):
        report_data = {
            "scenario_id": scenario.id,
            "scenario_type": scenario.type,
            "scenario_description": scenario.description,
            "scenario_source": str(scenario.source) if scenario.source else None,
            "reference_data": scenario.reference_data,
            "reference_options": scenario.reference_options,
        }
        # Add scenario type-specific fields if they exist
        if hasattr(scenario, 'backend'):
            report_data["scenario_backend"] = scenario.backend
        if hasattr(scenario, 'process_id'):
            report_data["process_id"] = scenario.process_id
        elif hasattr(scenario, 'application'):
            report_data["application"] = scenario.application
        if hasattr(scenario, 'endpoint'):
            report_data["endpoint"] = scenario.endpoint
        
        report_path = tmp_path / "benchmark_report.json"
        report_path.write_text(json.dumps(report_data, indent=2))
        upload_assets_on_fail(report_path)

    def _on_phase_exception(phase: str, exc: Exception):
        if report_path is not None:
            report = json.loads(report_path.read_text())
            report["test_failed"] = True
            report["test_failed_phase"] = phase
            report["test_error_message"] = str(exc)
            report_path.write_text(json.dumps(report, indent=2))
            cwd_report_dir = Path("benchmark_reports")
            cwd_report_dir.mkdir(exist_ok=True)
            (cwd_report_dir / f"{scenario.id}_benchmark_report.json").write_text(
                json.dumps(report, indent=2)
            )
            report_url = upload_assets_on_fail.get_url(report_path)
            if report_url:
                exc.add_note(f"Benchmark report: {report_url}")

    track_phase.on_exception = _on_phase_exception

    artifacts = None

    # with track_phase(phase="create-job"):
    #     runner.create_job()

    # with track_phase(phase="run-job"):
    #     max_minutes = request.config.getoption("--maximum-job-time-in-minutes")
    #     runner.run_job(max_minutes=max_minutes)

    with track_phase(phase="collect-metadata"):
        artifacts = runner.collect_artifacts()
        if artifacts.job_id:
            track_metric("job_id", artifacts.job_id)
            if report_path is not None:
                report = json.loads(report_path.read_text())
                report["job_id"] = artifacts.job_id
                report_path.write_text(json.dumps(report, indent=2))

        collect_metrics_from_job_metadata(
            artifacts.job_metadata,
            track_metric=track_metric,
        )
        collect_metrics_from_results_metadata(
            artifacts.results_metadata,
            track_metric=track_metric,
        )

    with track_phase(phase="download-actual"):
        actual_dir = tmp_path / "actual"
        paths = runner.download_actual(actual_dir=actual_dir)
        # Upload assets on failure
        upload_assets_on_fail(*paths)

    # # Pre-compute S3 URLs for actual files (used in error messages and benchmark reports)
    # actual_s3_urls = {
    #     str(p.relative_to(actual_dir)): upload_assets_on_fail.get_url(p)
    #     for p in sorted(actual_dir.rglob("*")) if p.is_file()
    # }
    # actual_s3_urls = {k: v for k, v in actual_s3_urls.items() if v is not None}

    # with track_phase(phase="download-reference"):
    #     reference_dir = download_reference_data(
    #         scenario=scenario, reference_dir=tmp_path / "reference"
    #     )

    # if report_path is not None:
    #     report = json.loads(report_path.read_text())
    #     report["actual_files"] = {
    #         str(p.relative_to(actual_dir)): f"{p.stat().st_size / 1024:.1f} kb"
    #         for p in sorted(actual_dir.rglob("*")) if p.is_file()
    #     }
    #     ref_files = {}
    #     for p in sorted(reference_dir.rglob("*")):
    #         if not p.is_file():
    #             continue
    #         rel = p.relative_to(reference_dir)
    #         size_str = f"{p.stat().st_size / 1024:.1f} kb"
    #         actual_counterpart = actual_dir / rel
    #         if not actual_counterpart.exists():
    #             size_str += " (missing in actual)"
    #         elif actual_counterpart.stat().st_size != p.stat().st_size:
    #             size_str += f" (actual: {actual_counterpart.stat().st_size / 1024:.1f} kb)"
    #         ref_files[str(rel)] = size_str
    #     report["reference_files"] = ref_files
    #     if actual_s3_urls:
    #         report["actual_data"] = actual_s3_urls
    #     report_path.write_text(json.dumps(report, indent=2))
    #     # Also write to CWD so the report is accessible on Jenkins workspace
    #     cwd_report_dir = Path("benchmark_reports")
    #     cwd_report_dir.mkdir(exist_ok=True)
    #     (cwd_report_dir / f"{scenario.id}_benchmark_report.json").write_text(
    #         json.dumps(report, indent=2)
    #     )

    # with track_phase(
    #     phase="compare", describe_exception=analyse_results_comparison_exception
    # ):
    #     # Compare actual results with reference data
    #     try:
    #         assert_job_results_allclose(
    #             actual=actual_dir,
    #             expected=reference_dir,
    #             tmp_path=tmp_path,
    #             rtol=scenario.reference_options.get("rtol", 1e-3),
    #             atol=scenario.reference_options.get("atol", 1),
    #             pixel_tolerance=scenario.reference_options.get("pixel_tolerance", 1),
    #         )
    #     except AssertionError as e:
    #         msg = str(e)
    #         if scenario.reference_data:
    #             msg += "\n\nReference data URLs:"
    #             for name, url in scenario.reference_data.items():
    #                 msg += f"\n  {name}: {url}"
    #         if actual_s3_urls:
    #             msg += "\n\nActual data S3 URLs (uploaded on failure):"
    #             for name, url in actual_s3_urls.items():
    #                 msg += f"\n  {name}: {url}"
    #         raise AssertionError(msg) from None
