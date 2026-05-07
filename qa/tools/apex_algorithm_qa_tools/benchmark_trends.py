"""
Utilities for loading historical benchmark metrics from Parquet
and extracting per-scenario metric histories for adaptive baselines.

Usage::

    from apex_algorithm_qa_tools.benchmark_trends import (
        load_scenario_history,
        create_s3_filesystem,
    )

    fs = create_s3_filesystem()
    history = load_scenario_history(
        parquet_path="bucket/metrics/v0/metrics.parquet",
        scenario_id="max_ndvi_composite",
        filesystem=fs,
    )
"""

import logging
import os

_log = logging.getLogger(__name__)

# Default metric names tracked by collect_metrics_from_job_metadata
DEFAULT_PERFORMANCE_METRICS = [
    "costs",
    "usage:cpu:cpu-seconds",
    "usage:memory:mb-seconds",
    "usage:duration:seconds",
]


def create_s3_filesystem():
    """
    Create a PyArrow S3 filesystem using the same env vars
    as the track_metrics plugin.

    Uses ``APEX_ALGORITHMS_S3_ACCESS_KEY_ID``,
    ``APEX_ALGORITHMS_S3_SECRET_ACCESS_KEY``, and
    ``APEX_ALGORITHMS_S3_ENDPOINT_URL`` (with fallback to
    ``AWS_*`` variants).
    """
    import pyarrow.fs

    return pyarrow.fs.S3FileSystem(
        access_key=(
            os.environ.get("APEX_ALGORITHMS_S3_ACCESS_KEY_ID")
            or os.environ.get("AWS_ACCESS_KEY_ID")
        ),
        secret_key=(
            os.environ.get("APEX_ALGORITHMS_S3_SECRET_ACCESS_KEY")
            or os.environ.get("AWS_SECRET_ACCESS_KEY")
        ),
        endpoint_override=(
            os.environ.get("APEX_ALGORITHMS_S3_ENDPOINT_URL")
            or os.environ.get("AWS_ENDPOINT_URL")
        ),
    )


def load_scenario_history(
    parquet_path: str,
    scenario_id: str,
    *,
    filesystem=None,
    metric_names: list[str] | None = None,
) -> list[dict]:
    """
    Load historical metric values for a specific scenario from Parquet.

    Returns a list of dicts (one per successful run), each containing
    the metric values. Sorted by run time ascending (oldest first).

    :param parquet_path: Path to the Parquet dataset (S3 key without scheme,
        or local path).
    :param scenario_id: The scenario to filter for.
    :param filesystem: PyArrow filesystem (use :func:`create_s3_filesystem`
        for S3 access).
    :param metric_names: Metrics to extract. Defaults to
        :data:`DEFAULT_PERFORMANCE_METRICS`.
    :return: List of metric dicts from successful historical runs.
    """
    import pyarrow.dataset as ds

    if metric_names is None:
        metric_names = DEFAULT_PERFORMANCE_METRICS

    try:
        dataset = ds.dataset(parquet_path, filesystem=filesystem)
        table = dataset.to_table()
    except Exception as e:
        _log.warning(f"Could not load benchmark history from {parquet_path}: {e}")
        return []

    df = table.to_pandas()

    # Filter to this scenario's successful runs
    if "scenario_id" not in df.columns or "test:outcome" not in df.columns:
        _log.warning("History Parquet missing scenario_id or test:outcome columns")
        return []

    mask = (df["scenario_id"] == scenario_id) & (df["test:outcome"] == "passed")
    df = df[mask]

    if "test:start" in df.columns:
        df = df.sort_values("test:start")

    # Extract metric values
    history = []
    for _, row in df.iterrows():
        metrics = {}
        for name in metric_names:
            if name in row and row[name] is not None:
                try:
                    metrics[name] = float(row[name])
                except (ValueError, TypeError):
                    pass
        if metrics:
            history.append(metrics)

    _log.info(
        f"Loaded {len(history)} historical runs for scenario {scenario_id!r}"
    )
    return history
