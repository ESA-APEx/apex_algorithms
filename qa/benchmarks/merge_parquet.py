import argparse
import logging
import pyarrow
import pyarrow.parquet
import pyarrow.fs
import pyarrow.dataset

_log = logging.getLogger(__name__)

def merge_parquet_files(
    s3_endpoint, s3_client, s3_secret, s3_bucket, s3_region, output_path, s3_output=False
):
    """
    Merge multiple parquet files from an S3 bucket.

    Args:
        s3_endpoint: S3 endpoint URL for custom S3 services
        s3_client: S3 access key ID
        s3_secret: S3 secret access key
        s3_bucket: S3 bucket name (e.g., 'bucket-name')
        s3_region: S3 region name (e.g., 'default')
        output_path: Local file path or S3 path for output
        s3_output: If True, save to S3; if False, save locally
    """
    # Initialize S3 filesystem
    s3fs = pyarrow.fs.S3FileSystem(
        access_key=s3_client, secret_key=s3_secret, endpoint_override=s3_endpoint, region=s3_region
    )

    # Read the partitioned metadata
    _log.info(f"Reading parquet files from S3 bucket: {s3_bucket}")
    read_partitioning = pyarrow.dataset.partitioning(
        schema=pyarrow.schema(fields=[("test:start:YYYYMM", pyarrow.string())]),
        flavor=None,
    )

    table = pyarrow.parquet.read_table(
        f"{s3_bucket}/metrics/v1/metrics.parquet",
        filesystem=s3fs,
        schema=pyarrow.schema(
            [
                # TODO: automatically get this from latest metrics file?
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
        ),
        partitioning=read_partitioning,
    )

    # Write the merged table to the output path
    _log.info(f"Writing merged parquet file to {'S3' if s3_output else 'local'} path: {output_path}")
    write_partitioning = pyarrow.dataset.partitioning(
        schema=pyarrow.schema(fields=[("test:start:YYYYMM", pyarrow.string())]),
        flavor=None,
    )
    if s3_output:
        pyarrow.parquet.write_to_dataset(
            table=table,
            root_path=output_path,
            filesystem=s3fs,
            partitioning=write_partitioning,
            # existing_data_behavior="delete_matching",
            basename_template="part-{i}.parquet",
        )
    else:
        pyarrow.parquet.write_to_dataset(
            table=table,
            root_path=output_path,
            partitioning=write_partitioning,
            existing_data_behavior="delete_matching",
            basename_template="part-{i}.parquet",
        )


def main():
    parser = argparse.ArgumentParser(description="Merge parquet files from S3 bucket")
    parser.add_argument("--s3-endpoint", type=str, required=True, help="S3 endpoint URL")
    parser.add_argument("--s3-client", type=str, required=True, help="S3 access key ID")
    parser.add_argument("--s3-secret", type=str, required=True, help="S3 secret access key")
    parser.add_argument("--s3-region", type=str, default="default", help="S3 region name")
    parser.add_argument(
        "--s3-bucket",
        type=str,
        help="S3 bucket name (e.g., 'bucket-name')",
    )
    parser.add_argument("--output-path", type=str, help="Output file path (local or S3)")
    parser.add_argument(
        "--s3-output",
        action="store_true",
        help="Save merged file to S3 instead of locally",
    )

    args = parser.parse_args()

    merge_parquet_files(
        s3_endpoint=args.s3_endpoint,
        s3_client=args.s3_client,
        s3_secret=args.s3_secret,
        s3_bucket=args.s3_bucket,
        s3_region=args.s3_region,
        output_path=args.output_path,
        s3_output=args.s3_output,
    )


if __name__ == "__main__":
    main()
