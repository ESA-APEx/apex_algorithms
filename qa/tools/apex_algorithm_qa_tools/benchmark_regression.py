"""Performance regression helpers for benchmark metrics."""

import logging
import math
from statistics import median as _median

_log = logging.getLogger(__name__)


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

        if actual > ref["max"]:
            violations.append(
                f"[{scenario_id}] regression in {metric_name!r}: "
                f"actual={actual} exceeds max={ref['max']}"
            )

    return violations


def _compute_threshold(values: list[float]) -> float:
    """Compute adaptive threshold with median and scaled MAD (k=3.5)."""
    median = _median(values)
    scaled_mad = max(1.0, 1.4826 * _median([abs(v - median) for v in values]))
    return round(median + 3.5 * scaled_mad, 4)


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
                f"Skipping baseline for {name!r}: only {len(values)} valid sample(s) "
                f"available (need >= {min_samples})"
            )
            continue

        baselines[name] = {"max": _compute_threshold(values)}

    return baselines
