from __future__ import annotations

from pathlib import Path

from apex_algorithm_qa_tools.benchmarks.ogc import (
    collect_ogc_results,
    collect_ogc_job_metadata,
    create_ogc_api_client,
    create_ogc_job,
    download_ogc_results,
    get_auth_token,
    run_ogc_job,
)
from apex_algorithm_qa_tools.benchmarks.runners.base import (
    BenchmarkRunner,
    BenchmarkRunnerArtifacts,
)

from apex_algorithm_qa_tools.scenarios.ogc import OGCAPIBenchmarkScenario


class OGCBenchmarkRunner(BenchmarkRunner):
    def __init__(self, *, scenario: OGCAPIBenchmarkScenario, request):
        super().__init__(scenario=scenario, request=request)
        self.endpoint = scenario.endpoint
        self.namespace = scenario.namespace
        self.application = scenario.application
        self.result_details = scenario.results
        self.user_token = get_auth_token(
            endpoint=self.endpoint, keycloak_url=scenario.auth.url, keycloak_realm=scenario.auth.realm
        )
        self._api_client = create_ogc_api_client(
            user_token=self.user_token,
            endpoint=self.endpoint,
            namespace=self.namespace,
        )
        self._job = None
        self._results = None

    def create_job(self):
        self._job = create_ogc_job(
            scenario=self.scenario,
        )

    def run_job(self, *, max_minutes: int | None):
        if self._job is None:
            raise RuntimeError("Cannot run OGC API job before create_job().")
        self._job_id = run_ogc_job(
            api_client=self._api_client,
            scenario=self.scenario,
            user_token=self.user_token,
            job=self._job,
            max_minutes=max_minutes,
        )

    def collect_artifacts(self) -> BenchmarkRunnerArtifacts:
        self._job_id = "opensartoolkit-v2-2-1-k6wp5"
        if self._job_id is None:
            raise RuntimeError("Cannot collect OGC API metadata before run_job().")

        self._results = collect_ogc_results(
            api_client=self._api_client, job_id=self._job_id, user_token=self.user_token
        )
        return BenchmarkRunnerArtifacts(
            job_id=self._job_id,
            job_metadata=collect_ogc_job_metadata(
                api_client=self._api_client,
                job_id=self._job_id,
            ),
            results_metadata=self._results,
        )

    def download_actual(self, *, actual_dir: Path) -> list[Path]:
        if self._results is None:
            raise RuntimeError("Cannot download OGC API results before collect_artifacts().")
        return download_ogc_results(
            results_metadata=self._results,
            actual_dir=actual_dir,
            user_token=self.user_token,
            details=self.result_details,
        )
