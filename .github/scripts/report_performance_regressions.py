#!/usr/bin/env python3
"""Check for performance regressions in the latest benchmark runs.

Reads historical metrics from S3 parquet, computes adaptive baselines,
and checks the most recent run per scenario for cost regressions.

Usage::

    python report_performance_regressions.py \
        --s3-bucket apex-benchmarks \
        --s3-key metrics/v1/metrics.parquet
"""

import argparse
import datetime
import os
import sys

import pyarrow.dataset as ds

from apex_algorithm_qa_tools.benchmark_regression import check_reference_performance, compute_baselines
from apex_algorithm_qa_tools.common import create_s3_filesystem
from apex_algorithm_qa_tools.github_issue_handler import GithubApi, GithubContext, PerformanceRegressionInfo
from apex_algorithm_qa_tools.scenarios import get_benchmark_scenarios


def _scenario_id_from_nodeid(nodeid: str) -> str:
    """Derive scenario identifier from a pytest nodeid string."""
    if "[" in nodeid and nodeid.endswith("]"):
        return nodeid.rsplit("[", 1)[1][:-1]
    if "::" in nodeid:
        return nodeid.rsplit("::", 1)[1]
    return nodeid


def main():
    """Run weekly performance regression checks and report findings.

    CLI params:
        --s3-bucket: Required bucket name containing metrics parquet.
        --s3-key: Optional key/path to parquet data inside the bucket.
        Filtering is fixed to passed runs in the most recent 60 days.
        Metric is fixed to costs.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s3-bucket", required=True)
    parser.add_argument("--s3-key", default="metrics/v1/metrics.parquet")
    args = parser.parse_args()
    metric_name = "costs"
    test_outcome = "passed"
    max_age_days = 60
    print(f"[progress] Starting regression check for {args.s3_bucket}/{args.s3_key}")

    fs = create_s3_filesystem()
    parquet_path = f"{args.s3_bucket}/{args.s3_key}"

    print("[progress] Loading dataset schema")
    dataset = ds.dataset(parquet_path, filesystem=fs)
    required_columns = ["test:nodeid", metric_name, "test:outcome", "test:start"]
    missing_columns = [c for c in required_columns if c not in dataset.schema.names]
    if missing_columns:
        print(
            f"Benchmark metrics schema mismatch. Missing required column(s): {', '.join(missing_columns)}.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("[progress] Reading required columns into memory")
    metrics_df = dataset.to_table(columns=required_columns).to_pandas()
    print(f"[progress] Loaded {len(metrics_df)} total row(s)")
    metrics_df = metrics_df[metrics_df["test:outcome"] == test_outcome]
    print(f"[progress] Rows after outcome filter ({test_outcome}): {len(metrics_df)}")

    if metrics_df.empty:
        print("No benchmark rows found after applying filters.")
        return

    metrics_df["scenario_id"] = metrics_df["test:nodeid"].astype(str).map(_scenario_id_from_nodeid)
    metrics_df["test:start"] = metrics_df["test:start"].astype(float)
    cutoff_epoch = (
        datetime.datetime.now(tz=datetime.timezone.utc)
        - datetime.timedelta(days=max_age_days)
    ).timestamp()
    metrics_df = metrics_df[metrics_df["test:start"] >= cutoff_epoch]
    metrics_df = metrics_df.sort_values("test:start")
    print(f"[progress] Rows after age filter ({max_age_days} days): {len(metrics_df)}")

    if metrics_df.empty:
        print("No benchmark rows found after applying filters.")
        return

    scenario_metrics_by_id = {
        scenario_id: group[[metric_name]].to_dict("records")
        for scenario_id, group in metrics_df.groupby("scenario_id", sort=True)
    }
    total_scenarios = len(scenario_metrics_by_id)
    print(f"[progress] Evaluating {total_scenarios} scenario(s)")

    regression_messages = []
    rows = []
    benchmark_scenarios = None

    ctx = GithubContext()
    api = None
    if ctx.token and ctx.repository:
        api = GithubApi(repository=ctx.repository, token=ctx.token)
        print("[progress] GitHub issue reporting is enabled")
    else:
        print("[progress] GitHub issue reporting is disabled")

    for i, scenario_id in enumerate(sorted(scenario_metrics_by_id), start=1):
        if i == 1 or i % 25 == 0 or i == total_scenarios:
            print(f"[progress] Processing scenario {i}/{total_scenarios}: {scenario_id}")
        scenario_metrics = scenario_metrics_by_id[scenario_id]
        if len(scenario_metrics) < 3:
            rows.append(f"- **{scenario_id}**: insufficient history ({len(scenario_metrics)} runs)")
            continue

        history = scenario_metrics[:-1]
        latest = scenario_metrics[-1]

        # Baselines from all history; latest run is the check target
        baselines = compute_baselines(history, metric_names=[metric_name])
        metric_baseline = baselines.get(metric_name)
        if not metric_baseline:
            rows.append(f"- **{scenario_id}**: no {metric_name} baseline available")
            continue

        violations = check_reference_performance(
            scenario_id=scenario_id,
            reference_performance={metric_name: metric_baseline},
            tracked_metrics=latest,
        )
        if violations:
            regression_messages.extend(violations)
            violation_text = "; ".join(violations)
            rows.append(f"- **{scenario_id}**: regression — {violation_text}")

            # Report issue
            if api:
                if benchmark_scenarios is None:
                    benchmark_scenarios = {s.id: s for s in get_benchmark_scenarios()}
                regression_info = PerformanceRegressionInfo(
                    scenario_id=scenario_id,
                    github_context=ctx,
                    violation=violation_text,
                    baseline=metric_baseline,
                    latest_metrics=latest,
                    scenario=benchmark_scenarios.get(scenario_id),
                )
                title = regression_info.issue_title()
                body = regression_info.build_issue_body()
                labels = regression_info.issue_labels()
                existing = next(
                    (i for i in api.list_issues(labels=["performance-regression"]) if i["title"] == title),
                    None,
                )
                if existing:
                    api.create_issue_comment(existing["number"], body)
                else:
                    api.create_issue(title=title, body=body, labels=labels)
        else:
            rows.append(f"- **{scenario_id}**: ok ({metric_name}={latest.get(metric_name, 'n/a')})")

    # Write GitHub step summary
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write("## Performance Regression Check\n\n")
            if regression_messages:
                f.write(f"**{len(regression_messages)} regression(s) detected.**\n\n")
            else:
                f.write("**No regressions detected.**\n\n")
            f.write("\n".join(rows) + "\n")

    print("\n".join(rows))
    print(f"[progress] Completed. Regressions detected: {len(regression_messages)}")

    if regression_messages:
        print(f"\n{len(regression_messages)} regression(s) detected.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
