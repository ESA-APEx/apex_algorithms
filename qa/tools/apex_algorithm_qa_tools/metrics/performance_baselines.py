"""Build robust baseline thresholds and detect performance regressions."""

import logging
import math
from statistics import median

_log = logging.getLogger(__name__)


def compute_threshold_stats(
    values: list[float], *, k: float = 3.0, min_band: float = 2.0
) -> dict[str, float | int]:
    """Compute MAD-based threshold statistics for one metric sample series.

    The acceptance band is defined as ``max(min_band, k * scaled_MAD)``.
    """
    median_value = median(values)
    mad_raw = median([abs(value - median_value) for value in values])
    mad_scaled_raw = 1.4826 * mad_raw
    band = max(min_band, k * mad_scaled_raw)
    mad_scaled = band / k
    upper_limit = round(median_value + band, 4)
    lower_limit = round(max(0.0, median_value - band), 4)
    return {
        "observations": len(values),
        "median": median_value,
        "mad_raw": mad_raw,
        "mad_scaled_raw": mad_scaled_raw,
        "mad_scaled": mad_scaled,
        "k": k,
        "min_band": min_band,
        "band": band,
        "threshold": upper_limit,
        "upper_limit": upper_limit,
        "lower_limit": lower_limit,
    }


def check_reference_performance(
    scenario_id: str,
    reference_performance: dict,
    tracked_metrics: dict,
) -> list[str]:
    """Compare tracked metrics against computed performance baselines."""
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


def compute_baselines(
    historical_values: list[dict],
    metric_names: list[str],
    min_samples: int = 3,
    max_samples: int = 20,
) -> dict:
    """Compute adaptive baselines from historical benchmark values."""
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
                "Skipping baseline for %r: only %s valid sample(s) available (need >= %s)",
                name,
                len(values),
                min_samples,
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
