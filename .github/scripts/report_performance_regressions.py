#!/usr/bin/env python3
"""Check for performance regressions in the latest benchmark runs.

Reads historical metrics from S3 parquet, computes adaptive baselines,
and checks the most recent run per scenario for cost regressions.

Usage::

    python check_performance_regressions.py \
        --s3-bucket apex-benchmarks \
        --s3-key metrics/v1/metrics.parquet
"""

import argparse
import os
import sys

import pyarrow.dataset as ds

from apex_algorithm_qa_tools.benchmark_history import load_scenario_metrics
from apex_algorithm_qa_tools.benchmark_regression import check_reference_performance, compute_baselines
from apex_algorithm_qa_tools.common import create_s3_filesystem
from apex_algorithm_qa_tools.github_issue_handler import GithubApi, GithubContext, PerformanceRegressionInfo
from apex_algorithm_qa_tools.scenarios import get_benchmark_scenarios


def main():
    """Run weekly performance regression checks and report findings.

    CLI params:
        --s3-bucket: Required bucket name containing metrics parquet.
        --s3-key: Optional key/path to parquet data inside the bucket.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s3-bucket", required=True)
    parser.add_argument("--s3-key", default="metrics/v1/metrics.parquet")
    parser.add_argument(
        "--metric-name",
        required=True,
        help="Metric used for baseline and regression checks.",
    )
    parser.add_argument(
        "--test-outcome",
        required=True,
        help="Outcome filter for historical runs (for example: passed). Use 'any' to disable.",
    )
    parser.add_argument(
        "--max-age-days",
        required=True,
        type=int,
        help="Maximum age of historical runs to consider.",
    )
    args = parser.parse_args()
    metric_name = args.metric_name
    test_outcome = None if args.test_outcome.lower() == "any" else args.test_outcome

    fs = create_s3_filesystem()
    parquet_path = f"{args.s3_bucket}/{args.s3_key}"

    scenario_ids = (
        ds.dataset(parquet_path, filesystem=fs)
        .to_table(columns=["scenario_id"])
        .to_pandas()["scenario_id"]
        .dropna()
        .unique()
        .tolist()
    )

    regression_messages = []
    rows = []
    benchmark_scenarios = None

    ctx = GithubContext()
    api = None
    if ctx.token and ctx.repository:
        api = GithubApi(repository=ctx.repository, token=ctx.token)

    for scenario_id in sorted(scenario_ids):
        scenario_metrics = load_scenario_metrics(
            parquet_path,
            scenario_id,
            filesystem=fs,
            metric_names=[metric_name],
            test_outcome=test_outcome,
            max_age_days=args.max_age_days,
        )
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

    if regression_messages:
        print(f"\n{len(regression_messages)} regression(s) detected.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
