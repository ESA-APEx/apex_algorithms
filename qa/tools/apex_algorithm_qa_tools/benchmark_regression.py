"""Performance regression helpers for benchmark metrics."""

import logging
import math
from statistics import median as _median

_log = logging.getLogger(__name__)


def compute_threshold_stats(
    values: list[float], *, k: float = 3.5, min_scaled_mad: float = 1.0
) -> dict[str, float]:
    """Compute MAD-based threshold statistics for one metric sample series."""
    median = _median(values)
    mad_raw = _median([abs(v - median) for v in values])
    mad_scaled_raw = 1.4826 * mad_raw
    mad_scaled = max(min_scaled_mad, mad_scaled_raw)
    threshold = round(median + k * mad_scaled, 4)
    return {
        "observations": float(len(values)),
        "median": float(median),
        "mad_raw": float(mad_raw),
        "mad_scaled_raw": float(mad_scaled_raw),
        "mad_scaled": float(mad_scaled),
        "k": float(k),
        "threshold": float(threshold),
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

        baselines[name] = {"max": _compute_threshold(values)}

    return baselines
