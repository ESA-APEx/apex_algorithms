"""
Reusable utilities to use in benchmarking
"""

import logging
from typing import Union

from apex_algorithm_qa_tools.pytest.pytest_track_metrics import MetricsTracker
from openeo.rest.job import BatchJob, JobResults

_log = logging.getLogger(__name__)

# Usage keys we expect every backend to report. Used purely for completeness
# warnings; absent keys do not fail the test, but they do disable adaptive
# regression checks on the corresponding metric for this run.
EXPECTED_USAGE_KEYS = ("cpu", "memory", "duration")


def collect_metrics_from_job_metadata(
    job_metadata: Union[BatchJob, dict],
    track_metric: MetricsTracker,
    expected_usage_keys: tuple = EXPECTED_USAGE_KEYS,
):
    if isinstance(job_metadata, BatchJob):
        job_metadata = job_metadata.describe()

    track_metric("costs", job_metadata.get("costs"))
    usage = job_metadata.get("usage", {}) or {}
    if not usage:
        _log.warning("No 'usage' metrics reported in job metadata")
    for usage_metric, usage_data in usage.items():
        if "unit" in usage_data and "value" in usage_data:
            track_metric(
                f"usage:{usage_metric}:{usage_data['unit']}", usage_data["value"]
            )

    # Completeness signal: which expected keys are missing from this run.
    missing = sorted(k for k in expected_usage_keys if k not in usage)
    if missing:
        _log.warning(
            f"Incomplete job usage metadata: missing expected keys {missing} "
            f"(present: {sorted(usage.keys())})"
        )
    track_metric("metrics:usage_complete", 0 if missing else 1)
    track_metric("metrics:usage_missing", ",".join(missing))


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
    *,
    max_age_days: int | None = 90,
    min_samples: int = 2,
    max_samples: int = 10,
) -> dict:
    """
    Compute adaptive performance baselines from historical runs.

    Each metric is treated independently: we keep all rows in the time window
    that actually contain that metric (up to ``max_samples`` most recent), and
    only compute a baseline if at least ``min_samples`` such rows exist. This
    means partial/incomplete metadata in some runs will only disable the
    affected metric, not the whole regression check.

    Threshold formula: ``mean + k(n) * σ`` where k linearly decreases from
    4.0 (n=2) to 2.0 (n=10), so few samples → wider band, many samples →
    tighter 2σ check.

    :param historical_values: List of dicts (oldest first). Each dict may
        contain a ``_datetime`` key (ISO 8601 string) for time-window filtering;
        rows with no/unparseable timestamp are kept regardless.
    :param metric_names: Metrics to compute baselines for. If None, auto-detects
        numeric metrics present anywhere in the history.
    :param max_age_days: Only consider runs newer than this many days. Set to
        ``None`` to disable time filtering.
    :param min_samples: Minimum number of historical observations required to
        compute a baseline for a given metric.
    :param max_samples: Cap on the number of most-recent observations used per
        metric.
    :return: Dict of ``{metric_name: {"max": threshold, "tolerance": 0, ...}}``
        ready for use with :func:`check_reference_performance`.
    """
    import math
    from datetime import datetime, timedelta, timezone

    if not historical_values:
        return {}

    # Time-window filter (per-row, not per-metric).
    if max_age_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        kept = []
        for row in historical_values:
            dt_str = row.get("_datetime")
            if dt_str:
                try:
                    dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass  # unparseable → keep, better than silently dropping
            kept.append(row)
        historical_values = kept

    if not historical_values:
        return {}

    # Auto-detect numeric metric names from history (union across all rows).
    if metric_names is None:
        names = set()
        for row in historical_values:
            for k, v in row.items():
                if isinstance(v, (int, float)) and not k.startswith("_"):
                    names.add(k)
        metric_names = sorted(names)

    baselines = {}
    for name in metric_names:
        # Per-metric: only rows that actually have this metric, most recent first.
        values = [
            row[name] for row in historical_values
            if isinstance(row.get(name), (int, float))
        ][-max_samples:]
        n = len(values)
        if n < min_samples:
            _log.debug(
                f"Skipping baseline for {name!r}: only {n} sample(s) "
                f"available (need >= {min_samples})"
            )
            continue

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
