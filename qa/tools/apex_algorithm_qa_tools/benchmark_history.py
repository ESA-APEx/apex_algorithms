"""
Utilities for loading historical benchmark metrics from Parquet
and extracting per-scenario metric histories for baseline computation.

Usage::

    from apex_algorithm_qa_tools.benchmark_history import (
        load_scenario_history,
        create_s3_filesystem,
    )

    fs = create_s3_filesystem()
    history = load_scenario_history(
        parquet_path="bucket/metrics/v1/metrics.parquet",
        scenario_id="max_ndvi_composite",
        filesystem=fs,
    )
"""

import datetime
import logging

import pandas as pd

from apex_algorithm_qa_tools.common import create_s3_filesystem  # noqa: F401 (re-exported for back-compat)

_log = logging.getLogger(__name__)


def _read_parquet(parquet_path: str, filesystem=None):
    """Load a Parquet dataset into a pandas DataFrame, handling schema evolution."""
    import pyarrow as pa
    import pyarrow.dataset as ds

    tables = [
        frag.to_table()
        for frag in ds.dataset(parquet_path, filesystem=filesystem).get_fragments()
    ]
    if not tables:
        return None
    return pa.concat_tables(tables, promote_options="permissive").to_pandas()


def _filter_by_test_outcome(df, test_outcome: str | None):
    """Filter to runs with specific pytest test outcome. None means no filtering."""
    if test_outcome is None:
        return df

    if "test:outcome" not in df.columns:
        _log.warning(
            "History Parquet missing test:outcome column; cannot filter by test outcome"
        )
        return df

    return df[df["test:outcome"] == test_outcome]


def _filter_by_age(df, time_col: str | None, max_age_days: int | None, scenario_id: str):
    """Filter out runs older than max_age_days. None means no filtering."""
    if max_age_days is None or time_col is None or df.empty:
        return df

    cutoff_dt = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(
        days=max_age_days
    )
    cutoff_epoch = cutoff_dt.timestamp()

    try:
        before = len(df)
        if time_col == "test:start":
            df[time_col] = df[time_col].astype(float)
            df = df[df[time_col] >= cutoff_epoch]
        else:
            df = df[
                df[time_col].apply(
                    lambda s: datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
                    .replace(tzinfo=datetime.timezone.utc)
                    .timestamp()
                    >= cutoff_epoch
                )
            ]
        dropped = before - len(df)
        if dropped:
            _log.info(
                f"Dropped {dropped} run(s) older than {max_age_days} days for scenario {scenario_id!r}"
            )
    except (ValueError, TypeError):
        _log.debug(f"Could not apply age filter on column {time_col!r}; skipping.")

    return df


def _load_scenario_runs(
    parquet_path: str,
    scenario_id: str,
    filesystem,
    test_outcome: str | None,
    max_age_days: int | None,
):
    """Load parquet and filter to relevant runs for a scenario.

    Returns (df, time_col). df may be empty if loading fails or no rows match.
    """
    try:
        df = _read_parquet(parquet_path, filesystem=filesystem)
        if df is None or df.empty:
            return pd.DataFrame(), None
    except Exception:
        _log.warning(f"Could not load benchmark history from {parquet_path}", exc_info=True)
        return pd.DataFrame(), None

    if "scenario_id" not in df.columns:
        _log.warning("History Parquet missing scenario_id column")
        return pd.DataFrame(), None

    df = df[df["scenario_id"] == scenario_id]
    df = _filter_by_test_outcome(df, test_outcome)

    time_col = next((c for c in ("test:start", "test:start:datetime") if c in df.columns), None)
    if time_col:
        df = df.sort_values(time_col)

    df = _filter_by_age(df, time_col, max_age_days, scenario_id)

    return df, time_col


def _extract_metrics(df, metric_names: list[str], time_col: str | None) -> list[dict]:
    """Extract metric values from dataframe rows into list of dicts."""
    history = []
    for _, row in df.iterrows():
        metrics = {}
        for name in metric_names:
            if name in row and row[name] is not None:
                try:
                    metrics[name] = float(row[name])
                except (ValueError, TypeError):
                    continue
        if metrics:
            if time_col and row.get(time_col) is not None:
                metrics["_datetime"] = str(row[time_col])
            history.append(metrics)
    return history


def load_scenario_history(
    parquet_path: str,
    scenario_id: str,
    *,
    filesystem=None,
    metric_names: list[str] | None = None,
    test_outcome: str | None = "passed",
    max_age_days: int | None = 90,
) -> list[dict]:
    """
    Load historical metric values for a specific scenario from Parquet.

    Returns a list of dicts (one per run), each containing the metric values.
    Sorted by run time ascending (oldest first).
    """

    df, time_col = _load_scenario_runs(
        parquet_path, scenario_id, filesystem, test_outcome, max_age_days
    )
    if df.empty:
        return []
    if metric_names is None:
        metric_names = sorted(
            {c for c in df.columns if c.startswith("usage:") or c == "costs"}
        )
    history = _extract_metrics(df, metric_names, time_col)

    _log.info(f"Loaded {len(history)} historical runs for scenario {scenario_id!r}")
    return history
