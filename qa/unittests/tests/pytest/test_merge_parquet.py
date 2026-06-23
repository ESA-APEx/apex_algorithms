import importlib.util
from pathlib import Path

import pyarrow
import pyarrow.dataset
import pyarrow.fs
import pyarrow.parquet
import pytest

# merge_parquet.py is a script in qa/benchmarks, not an installed package.
_spec = importlib.util.spec_from_file_location(
    "merge_parquet",
    Path(__file__).parents[3] / "benchmarks" / "merge_parquet.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
merge_parquet_files = _mod.merge_parquet_files

# S3 path where the benchmark suite writes its metrics.
_S3_METRICS_KEY = "metrics-unittests/v1/metrics-unittests.parquet"

# Schema that merge_parquet_files expects when reading.
_METRICS_SCHEMA = pyarrow.schema(
    [
        ("suite:run_id", pyarrow.string()),
        ("test:nodeid", pyarrow.string()),
        ("test:outcome", pyarrow.string()),
        ("test:start", pyarrow.float64()),
        ("test:start:YYYYMM", pyarrow.string()),
        ("test:start:datetime", pyarrow.string()),
        ("test:duration", pyarrow.float64()),
        ("test:phase:start", pyarrow.string()),
        ("test:phase:exception", pyarrow.string()),
        ("test:phase:end", pyarrow.string()),
        ("scenario_id", pyarrow.string()),
        ("job_id", pyarrow.string()),
        ("costs", pyarrow.float64()),
        ("usage:cpu:cpu-seconds", pyarrow.float64()),
        ("usage:memory:mb-seconds", pyarrow.float64()),
        ("usage:input_pixel:mega-pixel", pyarrow.float64()),
        ("usage:duration:seconds", pyarrow.float64()),
        ("usage:max_executor_memory:gb", pyarrow.float64()),
        ("usage:network_received:b", pyarrow.float64()),
        ("results:proj:shape:area:megapixel", pyarrow.float64()),
        ("results:proj:bbox:area:utm:km2", pyarrow.float64()),
    ]
)

_YYYYMM_PARTITIONING = pyarrow.dataset.partitioning(
    schema=pyarrow.schema(fields=[("test:start:YYYYMM", pyarrow.string())]),
    flavor=None,
)

# Two representative metrics rows covering different months.
_ROW_PASSED = {
    "suite:run_id": "run-001",
    "test:nodeid": "tests/test_benchmarks.py::test_run_benchmark[max_ndvi]",
    "test:outcome": "passed",
    "test:start": 1700000000.0,
    "test:start:YYYYMM": "2023-11",
    "test:start:datetime": "2023-11-14T22:13:20Z",
    "test:duration": 120.5,
    "test:phase:start": None,
    "test:phase:exception": None,
    "test:phase:end": None,
    "scenario_id": "max_ndvi",
    "job_id": "j-abc123",
    "costs": 0.5,
    "usage:cpu:cpu-seconds": 100.0,
    "usage:memory:mb-seconds": 2000.0,
    "usage:input_pixel:mega-pixel": 10.0,
    "usage:duration:seconds": 60.0,
    "usage:max_executor_memory:gb": 4.0,
    "usage:network_received:b": 1024.0,
    "results:proj:shape:area:megapixel": 1.5,
    "results:proj:bbox:area:utm:km2": 25.0,
}

_ROW_FAILED = {
    "suite:run_id": "run-002",
    "test:nodeid": "tests/test_benchmarks.py::test_run_benchmark[biopar]",
    "test:outcome": "failed",
    "test:start": 1702000000.0,
    "test:start:YYYYMM": "2023-12",
    "test:start:datetime": "2023-12-08T05:46:40Z",
    "test:duration": 90.0,
    "test:phase:start": "submit",
    "test:phase:exception": "submit:TimeoutError",
    "test:phase:end": None,
    "scenario_id": "biopar",
    "job_id": "j-def456",
    "costs": None,
    "usage:cpu:cpu-seconds": None,
    "usage:memory:mb-seconds": None,
    "usage:input_pixel:mega-pixel": None,
    "usage:duration:seconds": None,
    "usage:max_executor_memory:gb": None,
    "usage:network_received:b": None,
    "results:proj:shape:area:megapixel": None,
    "results:proj:bbox:area:utm:km2": None,
}


def _write_test_data_to_s3(
    s3fs: pyarrow.fs.S3FileSystem, s3_bucket: str, rows: list[dict]
) -> None:
    """Write a list of metrics rows to a mock S3 bucket using the same partitioned layout
    as the benchmark suite (YYYYMM directory partitioning, flavor=None)."""
    table = pyarrow.Table.from_pylist(rows, schema=_METRICS_SCHEMA)
    pyarrow.parquet.write_to_dataset(
        table=table,
        root_path=f"{s3_bucket}/{_S3_METRICS_KEY}",
        filesystem=s3fs,
        partitioning=_YYYYMM_PARTITIONING,
        basename_template="part-{i}.parquet",
    )


@pytest.fixture()
def s3fs(moto_server):
    """PyArrow S3FileSystem pointed at the mock S3 server."""
    return pyarrow.fs.S3FileSystem(
        access_key="test123",
        secret_key="test456",
        endpoint_override=moto_server,
        region="us-east-1",
    )


class TestMergeParquetFiles:
    def test_local_output_row_count_and_content(
        self, s3fs, s3_bucket, moto_server, tmp_path
    ):
        """Merging two partitioned parquet files from S3 to a local path produces
        a dataset that contains all source rows with their values intact."""
        _write_test_data_to_s3(s3fs=s3fs, s3_bucket=s3_bucket, rows=[_ROW_PASSED, _ROW_FAILED])

        output_path = str(tmp_path / "merged")
        merge_parquet_files(
            s3_endpoint=moto_server,
            s3_client="test123",
            s3_secret="test456",
            s3_bucket=s3_bucket,
            s3_region="us-east-1",
            input_path=_S3_METRICS_KEY,
            output_path=output_path,
            s3_output=False,
        )

        result = pyarrow.parquet.read_table(output_path, partitioning=_YYYYMM_PARTITIONING)
        assert result.num_rows == 2

        df = result.to_pandas().set_index("scenario_id")
        assert df.loc["max_ndvi"]["test:outcome"] == "passed"
        assert df.loc["max_ndvi"]["costs"] == pytest.approx(0.5)
        assert df.loc["biopar"]["test:outcome"] == "failed"
        assert df.loc["biopar"]["job_id"] == "j-def456"

    def test_s3_output_row_count_and_content(
        self, s3fs, s3_bucket, moto_server, tmp_path
    ):
        """Merging to an S3 output path produces a readable dataset with all source rows."""
        _write_test_data_to_s3(s3fs=s3fs, s3_bucket=s3_bucket, rows=[_ROW_PASSED, _ROW_FAILED])

        output_s3_path = "metrics-unittest/v1/metrics-unittests-merged.parquet"
        merge_parquet_files(
            s3_endpoint=moto_server,
            s3_client="test123",
            s3_secret="test456",
            s3_bucket=s3_bucket,
            s3_region="us-east-1",
            input_path=_S3_METRICS_KEY,
            output_path=output_s3_path,
            s3_output=True,
        )

        result = pyarrow.parquet.read_table(
            f"{s3_bucket}/{output_s3_path}", filesystem=s3fs, partitioning=_YYYYMM_PARTITIONING
        )
        assert result.num_rows == 2
        assert set(result.column("scenario_id").to_pylist()) == {"max_ndvi", "biopar"}

    def test_multiple_partitions_all_present(
        self, s3fs, s3_bucket, moto_server, tmp_path
    ):
        """Rows spread across three monthly partitions are all present after merging."""
        rows = [
            {**_ROW_PASSED, "test:start:YYYYMM": "2023-10", "scenario_id": "scenario-oct"},
            {**_ROW_PASSED, "test:start:YYYYMM": "2023-11", "scenario_id": "scenario-nov"},
            {**_ROW_PASSED, "test:start:YYYYMM": "2023-12", "scenario_id": "scenario-dec"},
        ]
        _write_test_data_to_s3(s3fs=s3fs, s3_bucket=s3_bucket, rows=rows)

        output_path = str(tmp_path / "merged")
        merge_parquet_files(
            s3_endpoint=moto_server,
            s3_client="test123",
            s3_secret="test456",
            s3_bucket=s3_bucket,
            s3_region="us-east-1",
            input_path=_S3_METRICS_KEY,
            output_path=output_path,
            s3_output=False,
        )

        result = pyarrow.parquet.read_table(output_path, partitioning=_YYYYMM_PARTITIONING)
        assert result.num_rows == 3
        assert set(result.column("scenario_id").to_pylist()) == {
            "scenario-oct",
            "scenario-nov",
            "scenario-dec",
        }

    def test_yyyymm_partition_column_reconstructed(
        self, s3fs, s3_bucket, moto_server, tmp_path
    ):
        """The test:start:YYYYMM column is correctly reconstructed from directory structure."""
        rows = [
            {**_ROW_PASSED, "test:start:YYYYMM": "2023-11", "scenario_id": "scenario-a"},
            {**_ROW_PASSED, "test:start:YYYYMM": "2023-12", "scenario_id": "scenario-b"},
        ]
        _write_test_data_to_s3(s3fs=s3fs, s3_bucket=s3_bucket, rows=rows)

        output_path = str(tmp_path / "merged")
        merge_parquet_files(
            s3_endpoint=moto_server,
            s3_client="test123",
            s3_secret="test456",
            s3_bucket=s3_bucket,
            s3_region="us-east-1",
            input_path=_S3_METRICS_KEY,
            output_path=output_path,
            s3_output=False,
        )

        result = pyarrow.parquet.read_table(output_path, partitioning=_YYYYMM_PARTITIONING)
        df = result.to_pandas().set_index("scenario_id")
        assert df.loc["scenario-a"]["test:start:YYYYMM"] == "2023-11"
        assert df.loc["scenario-b"]["test:start:YYYYMM"] == "2023-12"
