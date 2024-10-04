"""
Reusable utilities to use in benchmarking
"""

from typing import Union

from apex_algorithm_qa_tools.pytest.pytest_track_metrics import MetricsTracker
from openeo.rest.job import BatchJob, JobResults


def collect_metrics_from_job_metadata(
    job_metadata: Union[BatchJob, dict],
    track_metric: MetricsTracker,
):
    if isinstance(job_metadata, BatchJob):
        job_metadata = job_metadata.describe()

    track_metric("costs", job_metadata.get("costs"))
    for usage_metric, usage_data in job_metadata.get("usage", {}).items():
        if "unit" in usage_data and "value" in usage_data:
            track_metric(
                f"usage:{usage_metric}:{usage_data['unit']}", usage_data["value"]
            )


def collect_metrics_from_results_metadata(
    results_metadata: Union[BatchJob, JobResults, dict], track_metric: MetricsTracker
):
    if isinstance(results_metadata, BatchJob):
        results_metadata = results_metadata.get_results().get_metadata()
    elif isinstance(results_metadata, JobResults):
        results_metadata = results_metadata.get_metadata()

    proj_shape_area_mpx = []
    proj_shape_area_km2 = []
    for asset_name, asset_data in results_metadata.get("assets", {}).items():
        if "proj:shape" in asset_data:
            y, x = asset_data["proj:shape"][:2]
            proj_shape_area_mpx.append(y * x / 1e6)

            if "proj:epsg" in asset_data and "proj:bbox" in asset_data:
                epsg_code = int(asset_data["proj:epsg"])
                if (32601 <= epsg_code < 32660) or (32701 <= epsg_code < 32760):
                    # UTM zone: bbox coordinates are in meter -> calculate area in km2
                    w, s, e, n = asset_data["proj:bbox"][:4]
                    proj_shape_area_km2.append((n - s) * (e - w) / 1e6)

    # When there are multiple results, just report maximum for now
    if proj_shape_area_mpx:
        track_metric("results:proj:shape:area:megapixel", max(proj_shape_area_mpx))
    if proj_shape_area_km2:
        track_metric("results:proj:bbox:area:utm:km2", max(proj_shape_area_km2))
