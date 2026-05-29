from __future__ import annotations

import logging
from pathlib import Path

from apex_algorithm_qa_tools.benchmarks.openeo import (
    collect_openeo_metadata,
    create_openeo_connection,
    create_openeo_job,
    download_openeo_results,
    get_openeo_backend,
    run_openeo_job,
)
from apex_algorithm_qa_tools.benchmarks.runners.base import (
    BenchmarkRunner,
    BenchmarkRunnerArtifacts,
)

from apex_algorithm_qa_tools.scenarios import BenchmarkScenario

_log = logging.getLogger(__name__)


class OpenEOBenchmarkRunner(BenchmarkRunner):
    def __init__(self, *, scenario: BenchmarkScenario, request):
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
        return BenchmarkRunnerArtifacts(
            job_id=self._job.job_id,
            job_metadata=self._job.describe(),
            results_metadata=self._results.get_metadata(),
        )

    def download_actual(self, *, actual_dir: Path) -> list[Path]:
        if self._results is None:
            raise RuntimeError("Cannot download openEO results before collect_artifacts().")
        return download_openeo_results(results=self._results, actual_dir=actual_dir)
