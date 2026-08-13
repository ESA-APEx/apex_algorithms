from __future__ import annotations

import logging
from pathlib import Path

from apex_algorithm_qa_tools.benchmarks.openeo import (
    collect_openeo_metadata,
    create_openeo_connection,
    create_openeo_job,
    get_openeo_backend,
    run_openeo_job,
)
from apex_algorithm_qa_tools.benchmarks.runners.base import (
    BenchmarkJobMetadata,
    BenchmarkMetric,
    BenchmarkResults,
    BenchmarkRunner,
    BenchmarkRunnerArtifacts,
)

from apex_algorithm_qa_tools.scenarios.openeo import openEOBenchmarkScenario


_log = logging.getLogger(__name__)


class OpenEOBenchmarkRunner(BenchmarkRunner):
    def __init__(self, *, scenario: openEOBenchmarkScenario, request):
        super().__init__(scenario=scenario, request=request)
        self.backend = get_openeo_backend(scenario, request)
        self._connection = create_openeo_connection(
            backend=self.backend,
            origin=self.origin,
        )
        self._job = None
        self._results = None

    def create_job(self):
        self._job = create_openeo_job(
            connection=self._connection,
            scenario=self.scenario,
        )

    def run_job(self, *, max_minutes: int | None):
        if self._job is None:
            raise RuntimeError("Cannot run openEO job before create_job().")
        run_openeo_job(job=self._job, max_minutes=max_minutes)

    def collect_artifacts(self) -> BenchmarkRunnerArtifacts:
        if self._job is None:
            raise RuntimeError("Cannot collect openEO metadata before create_job().")

        self._results = collect_openeo_metadata(job=self._job)
        metadata = self._job.describe()
        usage_metrics = [
            BenchmarkMetric(name=name, unit=metric.get("unit"), value=metric.get("value"))
            for name, metric in (metadata.get("usage") or {}).items()
            if isinstance(metric, dict)
        ]
        return BenchmarkRunnerArtifacts(
            job_id=self._job.job_id,
            job_metadata=BenchmarkJobMetadata(
                cost=metadata.get("costs"),
                usage=usage_metrics,
            ),
            results_metadata=BenchmarkResults(
                assets=(self._results.get_metadata() or {}).get("assets", {}),
            ),
        )

    def download_actual(self, *, actual_dir: Path) -> list[Path]:
        if self._results is None:
            raise RuntimeError("Cannot download openEO results before collect_artifacts().")

        if self.scenario.reference_options.get("download_as_collection"):
            _log.info(f"Downloading results from {self._job.job_id} as STAC collection")
            paths = self._results.download_as_collection(
                target=actual_dir,
                download_derived_from=True,
                # path_templates=...
            )
        else:
            _log.info(f"Downloading results from {self._job.job_id} the old-school way")
            paths = self._results.download_files(target=actual_dir, include_stac_metadata=True)

        return paths
