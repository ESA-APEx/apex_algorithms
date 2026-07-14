#!/usr/bin/env python3
"""Check for performance regressions in the latest benchmark runs."""

import argparse
import datetime
import os
import sys

from apex_algorithm_qa_tools.common import create_s3_filesystem
from apex_algorithm_qa_tools.github_issue_handler import (
    GithubApi,
    GithubContext,
    PerformanceRegressionInfo,
)
from apex_algorithm_qa_tools.metrics.parquet_metrics import load_recent_scenario_metrics_map
from apex_algorithm_qa_tools.metrics.performance_baselines import (
    check_reference_performance,
    compute_baselines,
)
from apex_algorithm_qa_tools.scenarios import get_benchmark_scenarios


def main() -> None:
    """Run weekly performance regression checks and report findings."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s3-bucket", required=True)
    parser.add_argument("--s3-key", default="metrics/v1/metrics.parquet")
    args = parser.parse_args()

    metric_name = "costs"
    test_outcome = "passed"
    max_age_days = 90

    print(f"[progress] Starting regression check for {args.s3_bucket}/{args.s3_key}")
    filesystem = create_s3_filesystem()
    parquet_path = f"{args.s3_bucket}/{args.s3_key}"

    scenario_metrics_by_id = load_recent_scenario_metrics_map(
        parquet_path=parquet_path,
        filesystem=filesystem,
        metric_names=[metric_name],
        test_outcome=test_outcome,
        max_age_days=max_age_days,
    )
    print(f"[progress] Loaded history for {len(scenario_metrics_by_id)} scenario(s)")

    if not scenario_metrics_by_id:
        print("No benchmark rows found after applying filters.")
        return

    regression_messages = []
    rows = []

    benchmark_scenarios = {scenario.id: scenario for scenario in get_benchmark_scenarios()}
    total_scenarios = len(scenario_metrics_by_id)
    print(f"[progress] Evaluating {total_scenarios} scenario(s)")

    github_context = GithubContext()
    api = None
    if github_context.token and github_context.repository:
        api = GithubApi(repository=github_context.repository, token=github_context.token)
        print("[progress] GitHub issue reporting is enabled")
    else:
        print("[progress] GitHub issue reporting is disabled")

    for index, scenario_id in enumerate(sorted(scenario_metrics_by_id), start=1):
        if index == 1 or index % 25 == 0 or index == total_scenarios:
            print(f"[progress] Processing scenario {index}/{total_scenarios}: {scenario_id}")

        scenario_metrics = scenario_metrics_by_id[scenario_id]
        if len(scenario_metrics) < 3:
            rows.append(f"- **{scenario_id}**: insufficient history ({len(scenario_metrics)} runs)")
            continue

        history = scenario_metrics[:-1]
        latest = scenario_metrics[-1]

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

        if not violations:
            rows.append(f"- **{scenario_id}**: ok ({metric_name}={latest.get(metric_name, 'n/a')})")
            continue

        regression_messages.extend(violations)
        violation_text = "; ".join(violations)
        rows.append(f"- **{scenario_id}**: regression - {violation_text}")

        if not api:
            continue

        history_values = [
            float(row[metric_name])
            for row in history
            if isinstance(row.get(metric_name), (int, float))
        ]
        history_labels = [
            datetime.datetime.fromtimestamp(float(row["_timestamp"]), tz=datetime.timezone.utc).strftime(
                "%Y-%m-%d"
            )
            for row in history
            if row.get("_timestamp") is not None
        ]
        latest_label = "latest"
        if latest.get("_timestamp") is not None:
            latest_label = datetime.datetime.fromtimestamp(
                float(latest["_timestamp"]), tz=datetime.timezone.utc
            ).strftime("%Y-%m-%d")

        regression_info = PerformanceRegressionInfo(
            scenario_id=scenario_id,
            github_context=github_context,
            violation=violation_text,
            baseline=metric_baseline,
            latest_metrics=latest,
            history_values=history_values,
            history_labels=history_labels,
            latest_label=latest_label,
            metric_name=metric_name,
            scenario=benchmark_scenarios.get(scenario_id),
        )
        title = regression_info.issue_title()
        body = regression_info.build_issue_body()
        labels = regression_info.issue_labels()

        existing = next(
            (
                issue
                for issue in api.list_issues(labels=["performance-regression"])
                if issue["title"] == title
            ),
            None,
        )
        if existing:
            api.create_issue_comment(existing["number"], body)
        else:
            api.create_issue(title=title, body=body, labels=labels)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf8") as handle:
            handle.write("## Performance Regression Check\n\n")
            if regression_messages:
                handle.write(f"**{len(regression_messages)} regression(s) detected.**\n\n")
            else:
                handle.write("**No regressions detected.**\n\n")
            handle.write("\n".join(rows) + "\n")

    print("\n".join(rows))
    print(f"[progress] Completed. Regressions detected: {len(regression_messages)}")

    if regression_messages:
        print(f"\n{len(regression_messages)} regression(s) detected.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
