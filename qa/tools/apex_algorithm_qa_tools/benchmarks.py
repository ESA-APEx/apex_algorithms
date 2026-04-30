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


def _resolve_metric_name(short_name: str, tracked_metrics: dict) -> str:
    """
    Resolve a short metric name (e.g. "cpu:cpu-seconds", "memory:mb-seconds")
    to the full tracked metric name (e.g. "usage:cpu:cpu-seconds").

    If the short name already matches a tracked metric exactly, it is returned as-is.
    Otherwise, it looks for a tracked metric matching ``usage:{short_name}``.
    """
    if short_name in tracked_metrics:
        return short_name
    full = f"usage:{short_name}"
    if full in tracked_metrics:
        return full
    return short_name


def check_reference_performance(
    scenario_id: str,
    reference_performance: dict,
    tracked_metrics: dict,
    *,
    default_tolerance: float = 0.2,
) -> list[str]:
    """
    Compare tracked metrics against reference performance baselines.

    Metric names can be specified as short names (e.g. ``"cpu"``, ``"memory"``,
    ``"duration"``) which are automatically resolved to the full tracked metric
    name (e.g. ``"usage:cpu:cpu-seconds"``), or as full names.

    Returns a list of warning/violation messages for metrics that exceed
    ``max * (1 + tolerance)``.
    """
    violations = []
    for metric_name, ref in reference_performance.items():
        resolved_name = _resolve_metric_name(metric_name, tracked_metrics)
        max_val = ref["max"]
        tolerance = ref.get("tolerance", default_tolerance)
        actual = tracked_metrics.get(resolved_name)
        if actual is None:
            violations.append(
                f"[{scenario_id}] performance metric {metric_name!r}: "
                f"not found in tracked metrics (expected max={max_val})"
            )
            continue
        threshold = max_val * (1 + tolerance)
        if actual > threshold:
            violations.append(
                f"[{scenario_id}] performance regression in {metric_name!r} ({resolved_name}): "
                f"actual={actual} exceeds max={max_val} "
                f"(with tolerance={tolerance:.0%}, threshold={threshold})"
            )
    return violations


def analyse_results_comparison_exception(exc: Exception) -> Union[str, None]:
    if isinstance(exc, AssertionError):
        if "Differing 'derived_from' links" in str(exc):
            return "derived_from-change"
