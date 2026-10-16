from __future__ import annotations

import json
import logging
from pathlib import Path
from stac_pydantic.item import Item

from apex_algorithm_qa_tools.benchmarks.ogc import (
    get_ogc_results,
    process_ogc_results,
    collect_ogc_job_metadata,
    create_ogc_api_client,
    create_ogc_job,
    # download_ogc_results,
    download_ogc_results_headers,
    get_auth_token,
    run_ogc_job,
    extract_qualified_value_payload,
)
from apex_algorithm_qa_tools.benchmarks.runners.base import (
    BenchmarkRunner,
    BenchmarkRunnerArtifacts,
)
from apex_algorithm_qa_tools.scenarios import (
    BenchmarkScenario,
    download_reference_data,
)

from apex_algorithm_qa_tools.scenarios.ogc import OGCAPIBenchmarkScenario

_log = logging.getLogger(__name__)

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
        self._job_id = None
        self._api_result = None
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
        if self._job_id is None:
            raise RuntimeError("Cannot collect OGC API metadata before run_job().")

        result_response = get_ogc_results(
            api_client=self._api_client, job_id=self._job_id
        )
        self._api_result = result_response.copy()
        self._results = process_ogc_results(
            results=result_response, job_id=self._job_id, user_token=self.user_token
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

        # We currently don't need to download result assets,
        # we compare only the STAC items from the result FeatureCollection
        return []

        if self._results is None:
            raise RuntimeError("Cannot download OGC API results before collect_artifacts().")
        
        # Compare headers rather than entire files
        return download_ogc_results_headers(
            results_metadata=self._results,
            actual_dir=actual_dir,
            user_token=self.user_token,
            details=self.result_details,
        )

    def download_reference(self, scenario: BenchmarkScenario, reference_dir: Path) -> Path:
        headers = {
            "Authorization": f"Bearer {self.user_token}"
        }
        return download_reference_data(scenario, reference_dir, headers)

    def can_check_job_results_validity(self):
        return True

    def assert_job_results_validity(self, reference_dir: Path, actual_dir: Path):
        _log.info("Validating result")
        reference_files = reference_dir.glob("*")

        # Find reference FeatureCollection in reference dir
        ref_feature_collection = next((f for f in reference_files if f.as_uri().endswith(".json")), None)
        if not ref_feature_collection:
            raise RuntimeError("No JSON file (FeatureCollection) found in reference data.")

        with ref_feature_collection.open() as f:
            ref_feature_collection_json = json.loads(f.read())

        ref_features = ref_feature_collection_json.get("features")
        if not ref_features:
            _log.info(f"Reference file content: {json.dumps(ref_feature_collection_json)}")
            raise RuntimeError("No Feature (STAC Item) found in reference FeatureCollection.")

        act_features = None
        # Get actual FeatureCollection from this instance
        for key, value in self._api_result.items():
            instance = extract_qualified_value_payload(value.actual_instance)
            if "features" in instance:
                act_features = instance.get("features")
                break

        if not act_features:
            # Should never happen
            raise RuntimeError("No features found in actual result.")

        for ref_feature in ref_features:
            ref_item = Item.model_validate(ref_feature)
            act_feature = next((f for f in act_features if f.get("id") == ref_item.id), None)
            if not act_feature:
                raise RuntimeError(f"Item '{ref_item.id} not found in actual result.")
            act_item = Item.model_validate(act_feature)

            _log.info(f"Validating result item '{ref_item.id}'")

            # Check if all asset keys exists in actual item
            missing_assets = []
            for asset_key, asset in ref_item.assets.items():
                if asset_key not in act_item.assets:
                    missing_assets.append(asset_key)

            if missing_assets:
                raise RuntimeError(f"Assets missing in result item '{ref_item.id}': {', '.join(missing_assets)}")
            else:
                _log.info(f"All {len(ref_item.assets)} asset(s) contained in actual result item")
