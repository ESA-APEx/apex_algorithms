"""
Utilities for loading historical benchmark metrics from Parquet
and extracting per-scenario metric histories for baseline computation.

Usage::

    from apex_algorithm_qa_tools.benchmark_history import load_scenario_metrics
    from apex_algorithm_qa_tools.common import create_s3_filesystem

    fs = create_s3_filesystem()
    history = load_scenario_metrics(
        parquet_path="bucket/metrics/v1/metrics.parquet",
        scenario_id="max_ndvi_composite",
        filesystem=fs,
    )
"""

import datetime
import logging

import pyarrow as pa
import pyarrow.dataset as ds

_log = logging.getLogger(__name__)


def _scenario_id_from_nodeid(nodeid: str) -> str:
    """Derive scenario identifier from a pytest nodeid string."""
    if "[" in nodeid and nodeid.endswith("]"):
        return nodeid.rsplit("[", 1)[1][:-1]
    if "::" in nodeid:
        return nodeid.rsplit("::", 1)[1]
    return nodeid


def load_scenario_metrics(
    parquet_path: str,
    scenario_id: str,
    *,
    filesystem=None,
    metric_names: list[str] | None = None,
    test_outcome: str | None = "passed",
    max_age_days: int | None = 60,
) -> list[dict]:
    """
    Load historical metric values for a specific scenario from Parquet.

    Args:
        parquet_path: S3/object-store path to the Parquet dataset.
        scenario_id: Scenario identifier to filter rows by.
        filesystem: Optional pyarrow filesystem used to access the dataset.
        metric_names: Optional metric columns to extract. If omitted, costs and
            usage:* columns are auto-detected.
        test_outcome: Optional pytest outcome filter (for example "passed").
            Set to None to keep all outcomes.
        max_age_days: Optional age filter in days. Older runs are discarded.

    Returns a list of dicts (one per run), each containing the metric values.
    Sorted by run time ascending (oldest first).
    """
    # Load parquet with schema evolution
    try:
        tables = [
            frag.to_table()
            for frag in ds.dataset(parquet_path, filesystem=filesystem).get_fragments()
        ]
        if not tables:
            return []
        df = pa.concat_tables(tables, promote_options="permissive").to_pandas()
    except Exception:
        _log.warning(f"Could not load benchmark history from {parquet_path}", exc_info=True)
        return []

    if df.empty:
        return []

    # Filter to scenario via test nodeid (single supported schema)
    if "test:nodeid" not in df.columns:
        return []
    derived_scenario_ids = df["test:nodeid"].astype(str).map(_scenario_id_from_nodeid)
    df = df[derived_scenario_ids == scenario_id]

    # Filter by test outcome
    if test_outcome and "test:outcome" in df.columns:
        df = df[df["test:outcome"] == test_outcome]

    # Sort by time
    time_col = next((c for c in ("test:start", "test:start:datetime") if c in df.columns), None)
    if time_col:
        df = df.sort_values(time_col)

    # Filter by age
    if max_age_days and time_col and not df.empty:
        cutoff_epoch = (
            datetime.datetime.now(tz=datetime.timezone.utc)
            - datetime.timedelta(days=max_age_days)
        ).timestamp()
        df[time_col] = df[time_col].astype(float)
        df = df[df[time_col] >= cutoff_epoch]

    if df.empty:
        return []

    # Auto-detect metrics if not specified
    if metric_names is None:
        metric_names = sorted(
            {c for c in df.columns if c.startswith("usage:") or c == "costs"}
        )

    # Extract to list of dicts
    history = df[metric_names + ([time_col] if time_col else [])].to_dict("records")
    if time_col:
        for row in history:
            row["_datetime"] = str(row.pop(time_col))

    _log.info(f"Loaded {len(history)} historical runs for scenario {scenario_id!r}")
    return history
