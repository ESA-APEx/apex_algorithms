# from __future__ import annotations

# import dataclasses
# from abc import ABC, abstractmethod
# from pathlib import Path
# from typing import Any

# from apex_algorithm_qa_tools.benchmark_execution_ogcapi import (
#     create_ogc_api_client,
#     download_ogc_results,
#     execute_ogc_process,
#     get_ogc_results,
#     serialize_ogc_results,
#     wait_for_ogc_job,
# )
# from apex_algorithm_qa_tools.benchmark_execution_openeo import (
#     collect_openeo_metadata,
#     create_openeo_connection,
#     create_openeo_job,
#     download_openeo_results,
#     run_openeo_job,
# )




# class OGCAPIBenchmarkRunner(BenchmarkRunner):
#     def __init__(self, *, scenario, backend: str):
#         super().__init__(scenario=scenario, backend=backend)
#         self._components, self._api_client = create_ogc_api_client(
#             backend=backend,
#             request_headers=scenario.request_headers,
#         )
#         self._job_id = None
#         self._status_info = None
#         self._results = None

#     def create_job(self):
#         self._job_id, self._status_info, self._results = execute_ogc_process(
#             scenario=self.scenario,
#             components=self._components,
#             api_client=self._api_client,
#         )

#     def run_job(self, *, max_minutes: int | None):
#         if self._job_id is None:
#             return

#         self._status_info = wait_for_ogc_job(
#             components=self._components,
#             api_client=self._api_client,
#             job_id=self._job_id,
#             max_minutes=max_minutes,
#         )

#     def collect_artifacts(self) -> BenchmarkRunnerArtifacts:
#         if self._results is None and self._job_id is not None:
#             self._results = get_ogc_results(
#                 components=self._components,
#                 api_client=self._api_client,
#                 job_id=self._job_id,
#             )

#         if not isinstance(self._results, dict):
#             raise RuntimeError("OGC API execution did not return a result mapping")

#         job_metadata = self._status_info.to_dict() if self._status_info else {}
#         return BenchmarkRunnerArtifacts(
#             job_id=self._job_id,
#             job_metadata=job_metadata,
#             results_metadata=serialize_ogc_results(self._results),
#         )

#     def download_actual(self, *, actual_dir: Path) -> list[Path]:
#         if not isinstance(self._results, dict):
#             raise RuntimeError("OGC API execution did not return a result mapping")

#         return download_ogc_results(
#             results=self._results,
#             actual_dir=actual_dir,
#             request_headers=self._api_client.default_headers,
#         )