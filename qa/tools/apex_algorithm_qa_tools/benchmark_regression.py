"""Performance regression helpers for benchmark metrics."""

import logging
import math
from statistics import median as _median

_log = logging.getLogger(__name__)


def compute_threshold_stats(
    values: list[float], *, k: float = 3.5, min_band: float = 2.0
) -> dict[str, float]:
    """Compute MAD-based threshold statistics for one metric sample series.

    The acceptance band is defined as ``max(min_band, k * scaled_MAD)``.
    """
    median = _median(values)
    mad_raw = _median([abs(v - median) for v in values])
    mad_scaled_raw = 1.4826 * mad_raw
    band = max(min_band, k * mad_scaled_raw)
    mad_scaled = band / k
    upper_limit = round(median + band, 4)
    lower_limit = round(max(0.0, median - band), 4)
    return {
        "observations": float(len(values)),
        "median": float(median),
        "mad_raw": float(mad_raw),
        "mad_scaled_raw": float(mad_scaled_raw),
        "mad_scaled": float(mad_scaled),
        "k": float(k),
        "min_band": float(min_band),
        "band": float(band),
        "threshold": float(upper_limit),
        "upper_limit": float(upper_limit),
        "lower_limit": float(lower_limit),
    }


def check_reference_performance(
    scenario_id: str,
    reference_performance: dict,
    tracked_metrics: dict,
) -> list[str]:
    """Compare tracked metrics against computed performance baselines.

    Args:
        scenario_id: Scenario identifier used in violation messages.
        reference_performance: Mapping of metric name to threshold dict
            (expects a "max" value for each metric).
        tracked_metrics: Metric values for the run being validated.

    Returns:
        A list of human-readable regression messages.
    """
    violations = []
    for metric_name, ref in reference_performance.items():
        actual = tracked_metrics.get(metric_name)
        if actual is None:
            continue

        if "min" in ref and actual < ref["min"]:
            violations.append(
                f"[{scenario_id}] regression in {metric_name!r}: "
                f"actual={actual} below min={ref['min']}"
            )

        if actual > ref["max"]:
            violations.append(
                f"[{scenario_id}] regression in {metric_name!r}: "
                f"actual={actual} exceeds max={ref['max']}"
            )

    return violations


def _compute_threshold(values: list[float]) -> float:
    """Compute adaptive threshold with median and scaled MAD (k=3.5).

    Args:
        values: Numeric sample values for one metric.

    Returns:
        Regression threshold upper bound.
    """
    return compute_threshold_stats(values)["threshold"]


def compute_baselines(
    historical_values: list[dict],
    metric_names: list[str],
    min_samples: int = 3,
    max_samples: int = 20,
) -> dict:
    """Compute adaptive baselines from historical benchmark values.

    Args:
        historical_values: Time-ordered metric rows from older runs.
        metric_names: Metric names to compute thresholds for.
        min_samples: Minimum valid samples required per metric.
        max_samples: Maximum number of most-recent samples to include.

    Returns:
        Mapping of metric name to threshold dict with "max".
    """
    if not historical_values:
        return {}

    baselines = {}
    for name in metric_names:
        values = [
            row[name]
            for row in historical_values
            if isinstance(row.get(name), (int, float)) and not math.isnan(row[name])
        ][-max_samples:]

        if len(values) < min_samples:
            _log.info(
                f"Skipping baseline for {name!r}: only {len(values)} valid sample(s) "
                f"available (need >= {min_samples})"
            )
            continue

        stats = compute_threshold_stats(values)
        baselines[name] = {
            "max": stats["upper_limit"],
            "min": stats["lower_limit"],
            "median": stats["median"],
            "mad_scaled": stats["mad_scaled"],
        }

    return baselines
