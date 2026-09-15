from __future__ import annotations

import dataclasses
import json
import logging
import mimetypes
import os
import re
import time
import urllib
from pathlib import Path
from urllib.parse import urlparse

from ogc_api_processes_client.api.result_api import ResultApi
from ogc_api_processes_client.api_client_wrapper import ApiClientWrapper
from ogc_api_processes_client.configuration import Configuration
from ogc_api_processes_client.models import StatusCode
from ogc_api_processes_client.models.link import Link as OgcLink
from ogc_api_processes_client.models.input_value_no_object import InputValueNoObject

from stac_pydantic.collection import Collection

from apex_algorithm_qa_tools.benchmarks.auth import get_token_with_client_credentials, get_token_with_device_flow
from apex_algorithm_qa_tools.benchmarks.common import (
    BenchmarkJobMetadata,
    download_file,
    ensure_safe_relative_target,
    to_jsonable,
)
from apex_algorithm_qa_tools.benchmarks.runners.base import BenchmarkResults
from apex_algorithm_qa_tools.scenarios.ogc import OGCAPIBenchmarkScenario, OGCAPIResults

from httpx import get as http_get, Response as HTTPXResponse


_log = logging.getLogger(__name__)

_TERMINAL_JOB_STATUSES = {StatusCode.SUCCESSFUL, StatusCode.FAILED, StatusCode.DISMISSED}

STAC_COLLECTION_SCHEMA = "https://schemas.stacspec.org/v1.0.0/collection-spec/json-schema/collection.json"

GEOJSON_FEATURECOLLECTION_SCHEMA = (
    "https://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/schemas/featureCollectionGeoJSON.yaml"
)

MIMETYPE_EXTENSION_MAP = {
    "image/tiff; application=geotiff; profile=cloud-optimized": ".tif"
}


def get_client_credentials_env_var(url: str) -> str:
    """
    Get client credentials env var name for a given backend URL.
    """
    if not re.match(r"https?://", url):
        url = f"https://{url}"
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname

    if hostname in {
        "processing.geohazards-tep.eu",
    }:
        return "OGC_AUTH_CLIENT_CREDENTIALS_GEOHAZARDS_TEP"
    else:
        raise ValueError(f"Unsupported backend: {url=} ({hostname=})")


def get_auth_token(endpoint: str, keycloak_url: str, keycloak_realm: str) -> str:
    # Support direct token via environment variable
    if "OGC_AUTH_TOKEN" in os.environ:
        token = os.environ["OGC_AUTH_TOKEN"]
        _log.info("Using auth token from OGC_AUTH_TOKEN environment variable")
        return token

    auth_env_var = get_client_credentials_env_var(endpoint)
    if auth_env_var in os.environ:
        client_credentials = os.environ[auth_env_var]
        client_id, _, client_secret = client_credentials.partition("/")
        if client_id and client_secret:
            return get_token_with_client_credentials(
                keycloak_url=keycloak_url,
                realm=keycloak_realm,
                client_id=client_id,
                client_secret=client_secret,
            )
        elif client_id and not client_secret:
            return get_token_with_device_flow(
                keycloak_url=keycloak_url,
                realm=keycloak_realm,
                client_id=client_id,
            )
        else:
            raise ValueError(
                f"Invalid client credentials format in env var {auth_env_var!r}. "
                f"Expected 'client_id/client_secret' or 'client_id/'. Got: {client_credentials!r}"
            )
    else:
        raise ValueError(
            f"No authentication credentials found for endpoint {endpoint!r}. "
            "Please set the environment variable "
            f"{auth_env_var!r} with value 'client_id/client_secret' or 'client_id/'."
            "Or set OGC_AUTH_TOKEN with a valid JWT token."
        )


def create_ogc_api_client(*, endpoint: str, namespace: str, user_token: str) -> ApiClientWrapper:
    config = Configuration(host=f"{endpoint}/{namespace}" if namespace else endpoint)

    additional_args = {}
    additional_args["header_name"] = "Authorization"
    additional_args["header_value"] = f"Bearer {user_token}"

    return ApiClientWrapper(configuration=config, **additional_args)


def create_ogc_job(*, scenario) -> dict:
    return {"inputs": {key: value for key, value in scenario.parameters.items()}}


def _get_job_headers(user_token: str) -> dict:
    headers = {
        "accept": "*/*",
        # "Prefer": "respond-async;return=representation",
        "Content-Type": "application/json",
    }

    headers["Authorization"] = f"Bearer {user_token}"
    return headers


def _split_job_id(job_id: str) -> tuple[str, ...]:
    parts = job_id.split(":", 1)
    if len(parts) != 2:
        return ("", job_id)
    return tuple(parts)


def run_ogc_job(
    *,
    api_client: ApiClientWrapper,
    scenario: OGCAPIBenchmarkScenario,
    user_token: str,
    job: dict,
    max_minutes: int | None,
) -> str:
    headers = _get_job_headers(user_token=user_token)
    deadline = time.monotonic() + max_minutes * 60 if max_minutes else None

    # Execute the job
    content = api_client.execute_simple(process_id=scenario.application, execute=job, _headers=headers)
    namespace, job_id = _split_job_id(job_id=content.job_id)

    # Check the status
    status = StatusCode.ACCEPTED
    while status not in _TERMINAL_JOB_STATUSES:
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError(f"Batch job {job_id} exceeded maximum allowed time of {max_minutes} minutes")
        time.sleep(5)
        status = api_client.get_status(job_id=job_id).status
        _log.info(f"Job {job_id} is still running with status {status}...")

    # Check for job failure
    if status == StatusCode.FAILED:
        raise RuntimeError(f"OGC API job {job_id} failed with status {status}")
    elif status == StatusCode.DISMISSED:
        raise RuntimeError(f"OGC API job {job_id} was dismissed with status {status}")

    _log.info(f"Job {job_id} completed successfully with status {status}")
    return job_id


def collect_ogc_job_metadata(*, api_client: ApiClientWrapper, job_id: str) -> BenchmarkJobMetadata:
    # status_api = StatusApi(api_client.api_client)
    # status = status_api.get_status(job_id=job_id)
    # Currently the status API is not returning any relevant metrics
    return BenchmarkJobMetadata(cost=None, usage=[])


def _extract_assets_from_feature_collection(feature_collection: dict, *, result_name: str, user_token: str) -> dict:
    assets: dict = {}
    for feature in feature_collection.get("features", []):
        feature_assets = feature.get("assets")
        if isinstance(feature_assets, dict):
            assets.update(feature_assets)
            continue

        # Some providers expose assets through an item link instead of inlining them in the feature.
        for link in feature.get("links", []):
            if "collection" == link.get("rel") and link.get("href"):
                collection_link: str = link.get("href")
                _log.debug(
                    f"GeoJSON FeatureCollection results: '{result_name}' "
                    f"points to a valid collection URL: {collection_link}"
                )

                response: HTTPXResponse = http_get(
                    collection_link,
                    follow_redirects=True,
                    headers={"Authorization": f"Bearer {user_token}"},
                )
                response.raise_for_status()
                collection = Collection.model_validate(response.json())
                _log.debug(f"Extracted collection '{collection.id}' with assets: {list(collection.assets.keys())}")
                assets.update(collection.to_dict().get("assets", {}))
                break
    return assets


def _extract_qualified_value_payload(qualified_value) -> object | None:
    value = qualified_value.value

    # Primary path for non-union values.
    payload = to_jsonable(value)
    if payload is not None:
        return payload

    # Fallback for union models where actual_instance is None but oneof validators are populated.
    for attr in (
        "oneof_schema_1_validator",
        "oneof_schema_2_validator",
        "oneof_schema_3_validator",
        "oneof_schema_4_validator",
        "oneof_schema_5_validator",
        "oneof_schema_6_validator",
        "oneof_schema_7_validator",
    ):
        if hasattr(value, attr):
            candidate = getattr(value, attr)
            if candidate is not None:
                return candidate

    return None


def collect_ogc_results(*, api_client: ApiClientWrapper, job_id: str, user_token: str) -> BenchmarkResults:
    result_api = ResultApi(api_client.api_client)
    results = result_api.get_result(job_id=job_id)
    assets = {}
    _log.info(f"Collecting OGC API results for job {job_id} with {len(results)} outputs...")
    for result_name, result_value in results.items():
        if not result_value.actual_instance:
            _log.debug(f"Ignoring result '{result_name}' with None value")
            continue

        if isinstance(result_value.actual_instance, InputValueNoObject) or isinstance(
            result_value.actual_instance, OgcLink
        ):
            _log.debug(f"Ignoring result '{result_name}' of unmanaged type {type(result_value)}")
            continue

        qualified_value = result_value.actual_instance
        if qualified_value.var_schema and qualified_value.var_schema.actual_instance:
            schema_reference = qualified_value.var_schema.actual_instance
            _log.debug(
                f"Processing result\n* Name: '{result_name}'\n"
                f"* media type: {qualified_value.media_type}\n"
                f"* Python type: {type(qualified_value.value)}\n"
                f"* schema {qualified_value.var_schema}..."
            )

            if not isinstance(schema_reference, str):
                _log.warning(
                    f"Processing result name: '{result_name}' can not be processed, "
                    f"schema of type {type(schema_reference)} not recognized"
                )
                continue

            if STAC_COLLECTION_SCHEMA == schema_reference:
                _log.info(f"STAC Collection found in results: '{result_name}'")
                collection_payload = _extract_qualified_value_payload(qualified_value)
                if not isinstance(collection_payload, dict):
                    _log.warning(
                        f"Processing result: '{result_name}' can not be processed, "
                        f"invalid STAC collection payload type {type(collection_payload)}"
                    )
                    continue
                collection = Collection.model_validate(collection_payload)
                _log.debug(f"Extracted collection '{collection.id}' with assets: {list(collection.assets.keys())}")
                assets.update(collection.assets.to_dict())
            elif GEOJSON_FEATURECOLLECTION_SCHEMA == schema_reference:
                _log.info(f"GeoJSON FeatureCollection found in results: '{result_name}'")
                feature_collection = _extract_qualified_value_payload(qualified_value)
                if not isinstance(feature_collection, dict):
                    _log.warning(
                        f"Processing result: '{result_name}' can not be processed, "
                        f"invalid GeoJSON payload type {type(feature_collection)}"
                    )
                    continue
                assets.update(
                    _extract_assets_from_feature_collection(
                        feature_collection,
                        result_name=result_name,
                        user_token=user_token,
                    )
                )
            else:
                _log.warning(
                    f"Processing result: '{result_name}' can not be processed, "
                    f"schema {schema_reference} not yet managed"
                )
    _log.debug(f"Collected {len(assets)} assets from OGC API results: {list(assets.keys())}")
    return BenchmarkResults(assets=assets)


def _extract_download_link_from_asset(asset: dict) -> str | None:
    """
    Extracts the download link from an asset dictionary. Checks if the `href` field is present and contains an HTTPS URL.
    If this is not the case, look for an alternative link in `alternate` field. If no valid link is found, return None.

    Args:
        asset (dict): The asset dictionary.

    Returns:
        str | None: The download link if available, otherwise None.
    """
    refs = [asset.get("href"), asset.get("alternate", {}).get("https", {}).get("href")]
    for href in refs:
        if href and href.startswith("https://"):
            return href
    return None


def download_ogc_results(
    *,
    results_metadata: BenchmarkResults,
    actual_dir: Path,
    user_token: str | None = None,
    details: OGCAPIResults | None = None,
) -> list[Path]:
    actual_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    _log.info(f"Downloading {len(results_metadata.assets)} OGC API results to {actual_dir=}")
    results_path = actual_dir / "job-results.json"
    results_path.write_text(json.dumps(dataclasses.asdict(results_metadata), indent=2), encoding="utf8")
    paths.append(results_path)

    for output_name, output_data in sorted(results_metadata.assets.items()):
        output_data = to_jsonable(output_data)
        _log.debug(f"Downloading OGC API result '{output_name}' to {actual_dir=}")
        if isinstance(output_data, dict):
            ref = _extract_download_link_from_asset(output_data)
            mimetype = output_data.get("type")
            if not ref:
                _log.warning(f"Result '{output_name}' does not contain a valid download link, skipping download.")
                continue

            file_name = _resolve_output_filename(output_name=output_name, href=ref, mimetype=mimetype)
            target = ensure_safe_relative_target(actual_dir, file_name)
            target.parent.mkdir(parents=True, exist_ok=True)
            download_file(
                ref,
                target,
                user_token=user_token,
            )
            paths.append(target)
        else:
            target = ensure_safe_relative_target(actual_dir, f"{output_name}.json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(output_data, indent=2), encoding="utf8")
            paths.append(target)

    return paths


def _resolve_output_filename(*, output_name: str, href: str, mimetype: str | None = None) -> str:
    parsed = urlparse(href)
    name = Path(parsed.path).name
    if name:
        has_extension = bool(Path(name).suffix)
        _log.debug(f"Result '{output_name}' download link '{href}' has filename '{name}' with extension: {has_extension}")
        if has_extension:
            return name
        else:
            _log.warning(
                f"Result '{output_name}' download link '{href}' does not contain a file extension, "
                f"falling back to using output name with mimetype-based extension using mimetype '{mimetype}'."
            )
            extension = MIMETYPE_EXTENSION_MAP.get(mimetype)
            if not extension and mimetype:
                extension = mimetypes.guess_extension(mimetype)
                _log.debug(f"Result '{output_name}' mimetype '{mimetype}' maps to extension: {extension}")
            if extension:
                return f"{output_name}{extension}"
    return f"{output_name}.bin"
