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

from apex_algorithm_qa_tools.benchmark_history import load_scenario_history
from apex_algorithm_qa_tools.benchmark_regression import check_reference_performance, compute_baselines
from apex_algorithm_qa_tools.common import create_s3_filesystem
from apex_algorithm_qa_tools.github_issue_handler import GithubApi, GithubContext, PerformanceRegressionInfo
from apex_algorithm_qa_tools.scenarios import get_benchmark_scenarios

_ISSUE_LABEL = "performance-regression"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s3-bucket", required=True)
    parser.add_argument("--s3-key", default="metrics/v1/metrics.parquet")
    args = parser.parse_args()

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

    # Load benchmark scenarios for rich metadata
    benchmark_scenarios = {s.id: s for s in get_benchmark_scenarios()}

    regressions = []
    rows = []

    for scenario_id in sorted(scenario_ids):
        history = load_scenario_history(parquet_path, scenario_id, filesystem=fs)
        if len(history) < 3:
            rows.append(f"- **{scenario_id}**: insufficient history ({len(history)} runs)")
            continue

        # Baselines from all history; latest run is the check target
        baselines = compute_baselines(history, metric_names=["costs"])
        cost_baseline = baselines.get("costs")
        if not cost_baseline:
            rows.append(f"- **{scenario_id}**: no cost baseline available")
            continue

        latest = history[-1]
        violations = check_reference_performance(
            scenario_id=scenario_id,
            reference_performance={"costs": cost_baseline},
            tracked_metrics=latest,
        )
        if violations:
            regressions.extend(violations)
            rows.append(f"- **{scenario_id}**: regression — {violations[0]}")
            
            # Report issue
            ctx = GithubContext()
            if ctx.token and ctx.repository:
                regression_info = PerformanceRegressionInfo(
                    scenario_id=scenario_id,
                    github_context=ctx,
                    violation=violations[0],
                    baseline=cost_baseline,
                    latest_metrics=latest,
                    scenario=benchmark_scenarios.get(scenario_id),
                )
                api = GithubApi(repository=ctx.repository, token=ctx.token)
                title = regression_info.issue_title()
                body = regression_info.build_issue_body()
                labels = regression_info.issue_labels()
                existing = next(
                    (i for i in api.list_issues(labels=[_ISSUE_LABEL]) if i["title"] == title),
                    None,
                )
                if existing:
                    api.create_issue_comment(existing["number"], body)
                else:
                    api.create_issue(title=title, body=body, labels=labels)
        else:
            rows.append(f"- **{scenario_id}**: ok (costs={latest.get('costs', 'n/a')})")

    # Write GitHub step summary
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write("## Performance Regression Check\n\n")
            if regressions:
                f.write(f"**{len(regressions)} regression(s) detected.**\n\n")
            else:
                f.write("**No regressions detected.**\n\n")
            f.write("\n".join(rows) + "\n")

    print("\n".join(rows))

    if regressions:
        print(f"\n{len(regressions)} regression(s) detected.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
