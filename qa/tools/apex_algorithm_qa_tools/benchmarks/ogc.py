# from __future__ import annotations

# import importlib
# import json
# import time
# from pathlib import Path
# from typing import Any

# import requests
# from apex_algorithm_qa_tools.benchmark_execution_shared import (
#     ensure_safe_relative_target,
#     to_jsonable,
# )


# def load_ogc_api_components() -> dict[str, Any]:
#     try:
#         package = importlib.import_module("ogc_api_processes_client")
#         execute_api = importlib.import_module(
#             "ogc_api_processes_client.api.execute_api"
#         )
#         status_api = importlib.import_module(
#             "ogc_api_processes_client.api.status_api"
#         )
#         result_api = importlib.import_module(
#             "ogc_api_processes_client.api.result_api"
#         )
#         execute_model = importlib.import_module(
#             "ogc_api_processes_client.models.execute"
#         )
#     except ModuleNotFoundError as e:
#         raise RuntimeError(
#             "OGC API processes benchmark requires dependency "
#             "'ogc-api-processes-client'"
#         ) from e

#     return {
#         "ApiClient": package.ApiClient,
#         "Configuration": package.Configuration,
#         "ExecuteApi": execute_api.ExecuteApi,
#         "StatusApi": status_api.StatusApi,
#         "ResultApi": result_api.ResultApi,
#         "Execute": execute_model.Execute,
#     }


# def create_ogc_api_client(
#     *,
#     backend: str,
#     request_headers: dict | None,
# ):
#     components = load_ogc_api_components()
#     configuration = components["Configuration"](host=backend)
#     api_client = components["ApiClient"](configuration=configuration)

#     if request_headers:
#         api_client.default_headers.update(request_headers)

#     return components, api_client


# def execute_ogc_process(*, scenario, components: dict[str, Any], api_client):
#     execute_api = components["ExecuteApi"](api_client)
#     execute_request = {"inputs": scenario.inputs or {}}
#     if scenario.outputs is not None:
#         execute_request["outputs"] = scenario.outputs
#     if scenario.response is not None:
#         execute_request["response"] = scenario.response

#     execute_response = execute_api.execute_with_http_info(
#         process_id=scenario.process_id,
#         execute=components["Execute"].from_dict(execute_request),
#     )

#     if execute_response.status_code == 201:
#         status_info = execute_response.data
#         return status_info.job_id, status_info, None
#     if execute_response.status_code == 200:
#         return None, None, execute_response.data

#     raise RuntimeError(
#         "Unexpected HTTP status from OGC execute call: "
#         f"{execute_response.status_code}"
#     )


# def wait_for_ogc_job(*, components: dict[str, Any], api_client, job_id: str, max_minutes: int | None):
#     status_api = components["StatusApi"](api_client)
#     deadline = None
#     if max_minutes:
#         deadline = time.monotonic() + max_minutes * 60

#     while True:
#         status_info = status_api.get_status(job_id=job_id)
#         status = str(status_info.status)

#         if status == "successful":
#             return status_info
#         if status in {"failed", "dismissed"}:
#             raise RuntimeError(
#                 "OGC API process job "
#                 f"{job_id} ended in status {status!r}: "
#                 f"{status_info.message!r}"
#             )
#         if deadline is not None and time.monotonic() >= deadline:
#             raise TimeoutError(
#                 "OGC API process job "
#                 f"{job_id} exceeded maximum allowed time "
#                 f"of {max_minutes} minutes"
#             )

#         time.sleep(5)


# def get_ogc_results(*, components: dict[str, Any], api_client, job_id: str):
#     result_api = components["ResultApi"](api_client)
#     return result_api.get_result(job_id=job_id)


# def serialize_ogc_results(results: dict[str, Any]) -> dict[str, Any]:
#     return {name: to_jsonable(item) for name, item in results.items()}


# def _extract_result_href(item: Any) -> str | None:
#     value = to_jsonable(item)
#     if not isinstance(value, dict):
#         return None
#     if isinstance(value.get("href"), str):
#         return value["href"]
#     nested = value.get("value")
#     if isinstance(nested, dict) and isinstance(nested.get("href"), str):
#         return nested["href"]
#     return None


# def download_ogc_results(
#     *,
#     results: dict[str, Any],
#     actual_dir: Path,
#     request_headers: dict | None,
# ):
#     actual_dir.mkdir(parents=True, exist_ok=True)
#     serialized_results = serialize_ogc_results(results)

#     paths = []
#     metadata_path = actual_dir / "job-results.json"
#     metadata_path.write_text(json.dumps(serialized_results, indent=2))
#     paths.append(metadata_path)

#     for name, item in results.items():
#         href = _extract_result_href(item)
#         if not href:
#             continue

#         target = ensure_safe_relative_target(actual_dir, name)
#         target.parent.mkdir(parents=True, exist_ok=True)

#         response = requests.get(href, stream=True, headers=request_headers)
#         response.raise_for_status()
#         with target.open("wb") as f:
#             for chunk in response.iter_content(chunk_size=128 * 1024):
#                 f.write(chunk)
#         paths.append(target)

#     return paths
