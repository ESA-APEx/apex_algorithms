"""Load benchmark metric histories from Parquet datasets."""

import datetime
import logging

import pyarrow
import pyarrow.compute
import pyarrow.dataset

_log = logging.getLogger(__name__)


def scenario_id_from_nodeid(nodeid: str) -> str:
    """Derive scenario identifier from a pytest nodeid string."""
    if "[" in nodeid and nodeid.endswith("]"):
        return nodeid.rsplit("[", 1)[1][:-1]
    if "::" in nodeid:
        return nodeid.rsplit("::", 1)[1]
    return nodeid


def load_recent_scenario_metrics_map(
    parquet_path: str,
    *,
    filesystem=None,
    metric_names: list[str] | None = None,
    test_outcome: str | None = "passed",
    max_age_days: int | None = 60,
) -> dict[str, list[dict]]:
    """Load recent metric histories grouped by scenario id."""
    try:
        dataset = pyarrow.dataset.dataset(
            parquet_path,
            filesystem=filesystem,
        )
        schema_names = set(dataset.schema.names)

        if "test:nodeid" not in schema_names:
            return {}

        time_col = next(
            (
                candidate
                for candidate in ("test:start", "test:start:datetime")
                if candidate in schema_names
            ),
            None,
        )

        if metric_names is None:
            metric_names = sorted(
                {
                    column_name
                    for column_name in schema_names
                    if column_name.startswith("usage:") or column_name == "costs"
                }
            )

        missing_metrics = [name for name in metric_names if name not in schema_names]
        if missing_metrics:
            _log.warning("Missing metric columns in history dataset: %s", ", ".join(missing_metrics))
            return {}

        selected_columns = ["test:nodeid"] + metric_names
        if time_col:
            selected_columns.append(time_col)
        if test_outcome and "test:outcome" in schema_names:
            selected_columns.append("test:outcome")

        scan_filter = None
        if test_outcome and "test:outcome" in schema_names:
            scan_filter = pyarrow.compute.field("test:outcome") == test_outcome

        table = dataset.to_table(columns=selected_columns, filter=scan_filter)
        dataframe = table.to_pandas()
    except Exception:
        _log.warning("Could not load benchmark history from %s", parquet_path, exc_info=True)
        return {}

    if dataframe.empty or "test:nodeid" not in dataframe.columns:
        return {}

    if time_col and max_age_days and not dataframe.empty:
        cutoff_epoch = (
            datetime.datetime.now(tz=datetime.timezone.utc)
            - datetime.timedelta(days=max_age_days)
        ).timestamp()
        dataframe[time_col] = dataframe[time_col].astype(float)
        dataframe = dataframe[dataframe[time_col] >= cutoff_epoch]

    if dataframe.empty:
        return {}

    dataframe["scenario_id"] = dataframe["test:nodeid"].astype(str).map(scenario_id_from_nodeid)

    if time_col:
        dataframe = dataframe.sort_values(time_col)

    history_by_scenario: dict[str, list[dict]] = {}
    selected_columns = metric_names + ([time_col] if time_col else [])
    for scenario_id, group in dataframe.groupby("scenario_id", sort=True):
        history = group[selected_columns].to_dict("records")
        if time_col:
            for row in history:
                timestamp = float(row.pop(time_col))
                row["_timestamp"] = timestamp
                row["_datetime"] = datetime.datetime.fromtimestamp(
                    timestamp,
                    tz=datetime.timezone.utc,
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
        history_by_scenario[scenario_id] = history

    _log.info("Loaded history for %s scenario(s)", len(history_by_scenario))
    return history_by_scenario


def load_scenario_metrics(
    parquet_path: str,
    scenario_id: str,
    *,
    filesystem=None,
    metric_names: list[str] | None = None,
    test_outcome: str | None = "passed",
    max_age_days: int | None = 60,
) -> list[dict]:
    """Load historical metric values for a specific scenario from Parquet."""
    grouped_history = load_recent_scenario_metrics_map(
        parquet_path=parquet_path,
        filesystem=filesystem,
        metric_names=metric_names,
        test_outcome=test_outcome,
        max_age_days=max_age_days,
    )
    return grouped_history.get(scenario_id, [])
