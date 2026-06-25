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


def _compute_threshold(values: list[float]) -> dict:
    """Compute adaptive threshold with median and scaled MAD."""
    n = len(values)
    median = _median(values)
    scaled_mad = max(1.0, 1.4826 * _median([abs(v - median) for v in values]))
    k = 3.5
    threshold = median + k * scaled_mad

    return {
        "max": round(threshold, 4),
        "n_samples": n,
        "median": round(median, 4),
        "mad": round(scaled_mad, 4),
        "k": k,
    }


def compute_baselines(
    historical_values: list[dict],
    metric_names: list[str] | None = None,
    min_samples: int = 3,
    max_samples: int = 20,
) -> dict:
    """Compute adaptive baselines from historical benchmark values."""
    if not historical_values:
        return {}

    if metric_names is None:
        names = set()
        for row in historical_values:
            for k, v in row.items():
                if isinstance(v, (int, float)) and not k.startswith("_"):
                    names.add(k)
        metric_names = sorted(names)

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

        baselines[name] = _compute_threshold(values)

    return baselines
