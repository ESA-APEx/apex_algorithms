"""
Reusable utilities to use in benchmarking
"""

import logging
from typing import Union

from apex_algorithm_qa_tools.pytest.pytest_track_metrics import MetricsTracker
from openeo.rest.job import BatchJob, JobResults

_log = logging.getLogger(__name__)


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


def check_reference_performance(
    scenario_id: str,
    reference_performance: dict,
    tracked_metrics: dict,
    *,
    default_tolerance: float = 0.2,
) -> list[str]:
    """
    Compare tracked metrics against reference performance baselines.

    Returns a list of warning/violation messages for metrics that exceed
    ``max * (1 + tolerance)``.

    Metric names should match exactly as tracked (e.g. ``usage:cpu:cpu-seconds``,
    ``usage:memory:mb-seconds``, ``costs``, ``costs:per_km2``).
    """
    violations = []
    for metric_name, ref in reference_performance.items():
        max_val = ref["max"]
        tolerance = ref.get("tolerance", default_tolerance)
        actual = tracked_metrics.get(metric_name)
        if actual is None:
            # Metric not tracked — skip silently, only flag actual regressions
            continue
        threshold = max_val * (1 + tolerance)
        if actual > threshold:
            violations.append(
                f"[{scenario_id}] performance regression in {metric_name!r}: "
                f"actual={actual} exceeds max={max_val} "
                f"(with tolerance={tolerance:.0%}, threshold={threshold})"
            )
    return violations


def _adaptive_k(n: int) -> float:
    """
    Compute the adaptive multiplier for the performance threshold.

    Linearly interpolates from k=4.0 at n=2 to k=2.0 at n=10:
    ``k(n) = 4.0 - 0.25 * (n - 2)``
    """
    return 4.0 - 0.25 * (n - 2)


def compute_adaptive_baselines(
    historical_values: list[dict],
    metric_names: list[str] | None = None,
) -> dict:
    """
    Compute adaptive performance baselines from historical successful runs.

    Uses ``mean + k(n) * σ`` where k linearly decreases from 4.0 to 2.0
    as n goes from 2 to 10 (capped at 10 most recent runs):

    - n=1: no σ, uses 50% tolerance on the single value
    - n=2: k=4.0
    - n=5: k=3.25
    - n=10: k=2.0 (tightest, standard 2σ check)

    :param historical_values: List of dicts, each containing metric values
        from a successful benchmark run.
    :param metric_names: Metrics to compute baselines for. If None, auto-detects
        numeric metrics present in the history.
    :return: Dict of ``{metric_name: {"max": threshold, "tolerance": 0, ...}}``
        ready for use with :func:`check_reference_performance`.
    """
    import math

    if not historical_values:
        return {}

    # Only use the most recent runs (max 10) for baseline computation
    historical_values = historical_values[-10:]

    # Auto-detect numeric metric names from history
    if metric_names is None:
        metric_names = set()
        for row in historical_values:
            for k, v in row.items():
                if isinstance(v, (int, float)):
                    metric_names.add(k)
        metric_names = sorted(metric_names)

    baselines = {}
    for name in metric_names:
        values = [
            row[name] for row in historical_values
            if name in row and isinstance(row.get(name), (int, float))
        ]
        n = len(values)
        if n == 0:
            continue

        if n == 1:
            # Single observation: use it with 50% tolerance
            baselines[name] = {
                "max": values[0],
                "tolerance": 0.5,
                "source": "adaptive",
                "n_samples": 1,
            }
        else:
            mean = sum(values) / n
            variance = sum((v - mean) ** 2 for v in values) / (n - 1)
            std = math.sqrt(variance)
            k = _adaptive_k(n)
            threshold = mean + k * std
            baselines[name] = {
                "max": round(threshold, 4),
                "tolerance": 0,  # threshold already includes the adaptive band
                "source": "adaptive",
                "n_samples": n,
                "mean": round(mean, 4),
                "std": round(std, 4),
                "k": round(k, 2),
            }

    return baselines


def analyse_results_comparison_exception(exc: Exception) -> Union[str, None]:
    if isinstance(exc, AssertionError):
        if "Differing 'derived_from' links" in str(exc):
            return "derived_from-change"
