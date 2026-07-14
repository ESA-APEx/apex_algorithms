"""Build robust baseline thresholds and detect performance regressions."""

import logging
import math
from statistics import median

_log = logging.getLogger(__name__)


def _compute_threshold_stats(
    values: list[float], *, k: float = 3.0, min_margin: float = 2.0
) -> dict[str, float | int]:
    """Compute MAD-based threshold statistics for one metric sample series.

    The acceptance margin is defined as ``max(min_margin, k * scaled_MAD)``.
    """
    median_value = median(values)
    mad_raw = median([abs(value - median_value) for value in values])
    mad_scaled_raw = 1.4826 * mad_raw
    margin = max(min_margin, k * mad_scaled_raw)
    mad_scaled = margin / k
    upper_limit = round(median_value + margin, 4)
    lower_limit = round(max(0.0, median_value - margin), 4)
    return {
        "observations": len(values),
        "median": median_value,
        "mad_raw": mad_raw,
        "mad_scaled_raw": mad_scaled_raw,
        "mad_scaled": mad_scaled,
        "k": k,
        "min_margin": min_margin,
        "margin": margin,
        "threshold": upper_limit,
        "upper_limit": upper_limit,
        "lower_limit": lower_limit,
    }


def _check_reference_performance(
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

        lower_limit = ref.get("lower_limit")
        upper_limit = ref.get("upper_limit")

        if lower_limit is not None and actual < lower_limit:
            violations.append(
                f"[{scenario_id}] regression in {metric_name!r}: "
                f"actual={actual} below lower_limit={lower_limit}"
            )

        if upper_limit is not None and actual > upper_limit:
            violations.append(
                f"[{scenario_id}] regression in {metric_name!r}: "
                f"actual={actual} exceeds upper_limit={upper_limit}"
            )

    return violations


def _compute_baselines(
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

        stats = _compute_threshold_stats(values)
        baselines[name] = {
            "upper_limit": stats["upper_limit"],
            "lower_limit": stats["lower_limit"],
            "median": stats["median"],
            "mad_scaled": stats["mad_scaled"],
        }

    return baselines
