#%%
"""
Check available Parquet data on S3 for the biopar (BAP) scenario.
Validates that recent CI runs are correctly uploading usage metrics.
"""

import os
import time

os.environ["AWS_ACCESS_KEY_ID"] = "aacc3a7890a24f19979cbfde5c1fafc9"
os.environ["AWS_SECRET_ACCESS_KEY"] = "ae52d7200e814f8397648b1d1c1ab838"
os.environ["AWS_ENDPOINT_URL"] = "https://s3.waw3-1.cloudferro.com"
os.environ["AWS_S3_ENDPOINT"] = "s3.waw3-1.cloudferro.com"
os.environ["AWS_VIRTUAL_HOSTING"] = "FALSE"
os.environ["AWS_DEFAULT_REGION"] = "default"

import pyarrow.dataset as ds
import pyarrow as pa
import pandas as pd

BUCKET = "apex-benchmarks"
KEY = "metrics/v1/metrics.parquet"
SCENARIO_ID = "peakvalley"

# ---- Connect to S3 ----
s3 = pa.fs.S3FileSystem(
    access_key=os.environ["AWS_ACCESS_KEY_ID"],
    secret_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    endpoint_override=os.environ["AWS_ENDPOINT_URL"],
)
s3_path = f"{BUCKET}/{KEY}"

# ---- List all available partitions ----
from pyarrow.fs import FileSelector

print("Available partitions on S3:")
try:
    file_info = s3.get_file_info(FileSelector(s3_path, recursive=False))
    partitions = sorted([f.base_name for f in file_info if f.is_file is False])
    for p in partitions:
        print(f"  {p}")
except Exception as e:
    print(f"  Error listing: {e}")
    partitions = []

# ---- Load ALL partitions with unified schema (int->float to avoid truncation) ----
print(f"\nLoading all partitions...")
t0 = time.time()
dfs = []
for p in partitions:
    try:
        part_path = f"{s3_path}/{p}"
        raw_ds = ds.dataset(part_path, filesystem=s3, format="parquet")
        # Convert int columns to float64 to handle cross-partition schema conflicts
        new_fields = []
        for field in raw_ds.schema:
            if pa.types.is_integer(field.type):
                new_fields.append(field.with_type(pa.float64()))
            else:
                new_fields.append(field)
        unified = ds.dataset(part_path, filesystem=s3, format="parquet", schema=pa.schema(new_fields))
        dfs.append(unified.to_table().to_pandas())
    except Exception as e:
        print(f"  Skipping {p}: {e}")

if not dfs:
    raise RuntimeError("No data found")

df = pd.concat(dfs, ignore_index=True)
print(f"Loaded {len(df)} total rows in {time.time() - t0:.1f}s")

# ---- Find: last date we had full usage metrics, per metric ----
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 220)
pd.set_option("display.max_colwidth", 50)

ALL_USAGE = [
    "usage:cpu:cpu-seconds",
    "usage:memory:mb-seconds",
    "usage:duration:seconds",
    "usage:max_executor_memory:gb",
    "usage:network_received:b",
]
avail_metrics = [c for c in ALL_USAGE if c in df.columns]

df_sorted = df[df["job_id"].notna()].sort_values("test:start:datetime").copy()

print(f"\n{'='*80}")
print(f"  LAST DATE EACH METRIC WAS LOGGED")
print(f"{'='*80}")
print(f"\n{'Metric':<35} {'Last Seen':<24} {'Scenario':<30} {'Job ID'}")
print(f"{'─'*35} {'─'*24} {'─'*30} {'─'*50}")
for m in avail_metrics:
    has_m = df_sorted[df_sorted[m].notna()]
    if len(has_m):
        last_row = has_m.iloc[-1]
        print(f"  {m:<33} {last_row['test:start:datetime']:<24} {last_row['scenario_id']:<30} {last_row['job_id']}")
    else:
        print(f"  {m:<33} NEVER")

# Last 5 runs that had cpu (the metric most often missing)
print(f"\n\n{'='*80}")
print(f"  LAST 5 RUNS WITH usage:cpu:cpu-seconds")
print(f"{'='*80}")
if "usage:cpu:cpu-seconds" in df.columns:
    cpu_runs = df_sorted[df_sorted["usage:cpu:cpu-seconds"].notna()].tail(5)
    print(cpu_runs[["test:start:datetime", "scenario_id", "job_id", "usage:cpu:cpu-seconds"]].to_string(index=False))

# First run AFTER last complete that was missing cpu
print(f"\n\n{'='*80}")
print(f"  FIRST RUNS MISSING usage:cpu:cpu-seconds (after the last time it was present)")
print(f"{'='*80}")
if "usage:cpu:cpu-seconds" in df.columns:
    last_cpu_date = df_sorted[df_sorted["usage:cpu:cpu-seconds"].notna()]["test:start:datetime"].max()
    after_missing = df_sorted[
        (df_sorted["test:start:datetime"] > last_cpu_date) &
        (df_sorted["usage:cpu:cpu-seconds"].isna())
    ].head(10)
    if len(after_missing):
        print(f"  (Last cpu seen: {last_cpu_date})")
        print(after_missing[["test:start:datetime", "scenario_id", "job_id", "usage:duration:seconds"]].to_string(index=False))
    else:
        print("  No runs missing cpu after the last time it was present — all recent runs have it!")
# %%
