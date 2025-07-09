from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import logging
import os
import re
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
from apex_algorithm_qa_tools.scenarios import (
    BenchmarkScenario,
    get_benchmark_scenarios,
    get_project_root,
)

logger = logging.getLogger(__name__)


class GithubApi:
    """
    Generic GitHub API client for authenticated requests to a specific repository.
    """

    def __init__(self, repository: str, token: str):
        self._repo = repository
        self._token = token

    def request(
        self,
        *,
        method: str,
        path: str,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        expected_status: Optional[int] = 200,
        timeout: float = 10.0,
    ) -> dict:
        """
        Helper method to make authenticated requests to the GitHub API.
        """
        try:
            url = f"https://api.github.com/repos/{self._repo}/{path.lstrip('/')}"
            headers = {
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
            }
            logger.debug(f"Doing `{method} {url}` with {params=}")
            resp = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
                timeout=timeout,
            )
            logger.debug(f"Response: {resp!r}")
            resp.raise_for_status()
            if expected_status is not None and resp.status_code != expected_status:
                raise RuntimeError(
                    f"Unexpected status code {resp.status_code} (!= {expected_status}) for `{method} {url}`: {resp.text}"
                )
            return resp.json()
        except requests.HTTPError as e:
            raise RuntimeError(
                f"Failed to `{method} {url}`: {e=} {e.response.text=}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Failed to `{method} {url}`: {e=}") from e

    def list_issues(
        self, *, state: str = "open", labels: Optional[List[str]] = None
    ) -> List[dict]:
        """
        List (open) issues in the repository

        https://docs.github.com/en/rest/issues/issues?apiVersion=2022-11-28#list-repository-issues
        """
        params = {
            "state": state,
            "page": 1,  # TODO: handle pagination
        }
        if labels:
            params["labels"] = ",".join(labels)
        return self.request(method="GET", path="/issues", params=params)

    def create_issue(
        self, *, title: str, body: str, labels: Optional[List[str]] = None
    ) -> dict:
        """
        Create new issue under the repository.

        https://docs.github.com/en/rest/issues/issues?apiVersion=2022-11-28#create-an-issue
        """
        data = {
            "title": title,
            "body": body,
            "labels": labels or [],
        }
        resp = self.request(
            method="POST", path="/issues", data=data, expected_status=201
        )
        logger.info(
            f"Created new issue: #{resp.get('number')} {resp.get('title')!r} at {resp.get('url')}"
        )
        return resp

    def create_issue_comment(self, issue_number: int, body: str) -> dict:
        """
        Create a comment on an existing issue.

        https://docs.github.com/en/rest/issues/comments?apiVersion=2022-11-28#create-an-issue-comment
        """
        data = {"body": body}
        return self.request(
            method="POST",
            path=f"/issues/{issue_number}/comments",
            data=data,
            expected_status=201,
        )


class GithubContext:
    def __init__(self):
        # Environment variables set by GitHub Actions
        # TODO: get this from report/metrics instead of environment variables?
        self.server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com")
        self.repository = os.getenv("GITHUB_REPOSITORY", "ESA-APEx/apex_algorithms")
        self.run_id = os.getenv("GITHUB_RUN_ID")
        self.sha = os.getenv("GITHUB_SHA", "main")
        self.token = os.getenv("GITHUB_TOKEN")

    def get_workflow_run_url(self) -> str | None:
        """Link to current workflow run."""
        if self.repository and self.run_id:
            return f"{self.server_url}/{self.repository}/actions/runs/{self.run_id}"

    def get_file_permalink(self, path: str) -> str | None:
        """Permalink to a file in the repository at the specific commit."""
        if self.repository and self.sha:
            return f"{self.server_url}/{self.repository}/blob/{self.sha}/{path}"


@dataclasses.dataclass(frozen=True)
class TerminalReportSection:
    title: Union[str, None]
    subnodes: List[Union[str, TerminalReportSection]]


# Simple alias for now
TestMetricsData = Dict[str, Any]


class PytestReportParser:
    def parse_metrics_json(self, path: Path) -> List[TestMetricsData]:
        """
        Parse the metrics.json file to extract relevant metrics.
        Produces a list with of one dictionary per test/scenario run.
        """
        logger.info(f"Parsing metrics from {path}")
        with path.open("r", encoding="utf8") as f:
            metrics = json.load(f)

        def get_metric(metrics: List[list], name: str, default=None) -> Any:
            """Helper to extract a metric by name from the list of metrics."""
            found = [v for (k, v) in metrics if k == name]
            if len(found) == 0:
                return default
            elif len(found) == 1:
                return found[0]
            else:
                raise ValueError(f"Multiple values found for metric '{name}': {found}")

        # Flatten the data structure a bit for easier access
        # TODO: instead of simple dict: wrap this in some kind of data class structure?
        return [
            {
                "nodeid": m["nodeid"],
                "outcome": m["report"].get("outcome"),
                "start": m["report"].get("start"),
                "duration": m["report"].get("duration"),
                **{
                    k: get_metric(metrics=m["metrics"], name=k)
                    for k in [
                        "scenario_id",
                        "job_id",
                        "costs",
                        "test:phase:start",
                        "test:phase:end",
                        "test:phase:exception",
                    ]
                },
            }
            for m in metrics
        ]

    def parse_terminal_report_sections(self, path: Path) -> TerminalReportSection:
        """
        Parse sections from pytest terminal report, which are formatted as:

            ===== H1 =====
            _____ H2 _____
            ...

        Returns nested TerminalReportSection data structure.
        """
        logger.info(f"Parsing sections from terminal report dump {path}")

        root = TerminalReportSection(title="root", subnodes=[])
        current_section = root

        # regexes to find section headers ("===== H1 =====", "_____ H2 _____", ...)
        h1_regex = re.compile(r"^={4,}\s+(?P<title>.+)\s+={4,}$")
        h2_regex = re.compile(r"^_{4,}\s+(?P<title>.+)\s+_{4,}$")

        for line in path.open("r", encoding="utf8"):
            if match := h1_regex.match(line):
                # Start new h1 section
                current_section = TerminalReportSection(
                    title=match.group("title"), subnodes=[]
                )
                root.subnodes.append(current_section)
            elif match := h2_regex.match(line):
                # Start new h2 section within the current h1
                if not (
                    len(root.subnodes) > 0
                    and isinstance(root.subnodes[-1], TerminalReportSection)
                ):
                    # Ensure we have a preceding H1 section
                    root.subnodes.append(TerminalReportSection(title=None, subnodes=[]))
                current_section = TerminalReportSection(
                    title=match.group("title"), subnodes=[]
                )
                root.subnodes[-1].subnodes.append(current_section)
            else:
                current_section.subnodes.append(line.rstrip())

        return root

    def extract_failure_logs(self, path: Path) -> Dict[str, str]:
        """Extract per test failure logs from the terminal report."""
        logs = {}
        for l1_node in self.parse_terminal_report_sections(path).subnodes:
            if (
                isinstance(l1_node, TerminalReportSection)
                and l1_node.title == "FAILURES"
            ):
                for l2_node in l1_node.subnodes:
                    if isinstance(l2_node, TerminalReportSection):
                        # TODO: this assumes level 2 only has text lines,
                        #       and no further subsections, but that is ok for now.
                        logs[l2_node.title] = "\n".join(l2_node.subnodes).strip()
        return logs


@dataclasses.dataclass(frozen=True)
class ScenarioRunInfo:
    """Information about a benchmark scenario run"""

    scenario: BenchmarkScenario
    github_context: GithubContext
    test_metrics: TestMetricsData
    failure_logs: str | None = None

    def get_contacts(self) -> list | None:
        """Get contact information from corresponding OGC API record."""
        # Guess records path from benchmark scenario source.
        if isinstance(self.scenario.source, Path):
            paths = list(
                (self.scenario.source.parent.parent / "records").glob("*.json")
            )
            logger.info(
                f"Looking up contact info for {self.scenario.id} in {paths=} (from {self.scenario.source})"
            )
            for path in paths:
                try:
                    with path.open("r", encoding="utf8") as f:
                        record = json.load(f)
                    if contacts := record.get("properties", {}).get("contacts"):
                        return contacts
                except Exception as e:
                    logger.warning(f"Failed to read contacts from {path}: {e!r}")

    def get_scenario_link(self) -> str | None:
        """
        Generate a URL to the scenario definition file at the specific commit.
        """
        if isinstance(self.scenario.source, Path):
            path = self.scenario.source.relative_to(get_project_root()).as_posix()
            return self.github_context.get_file_permalink(path)

    def issue_title(self) -> str:
        return f"Scenario Failure: {self.scenario.id}"

    def build_workflow_run_overview(self) -> str:
        scenario_link = self.get_scenario_link()
        workflow_run_url = self.github_context.get_workflow_run_url()
        overview = textwrap.dedent(
            f"""
            **Benchmark scenario ID**: `{self.scenario.id}`
            **Benchmark scenario definition**: {scenario_link}
            **openEO backend**: {self.scenario.backend}
            """
        )
        if workflow_run_url:
            overview += textwrap.dedent(
                f"""
                **GitHub Actions workflow run**: {workflow_run_url}
                **Workflow artifacts**: {workflow_run_url}#artifacts
                """
            )
        overview += textwrap.dedent(
            f"""
            **Test start**: {datetime.datetime.fromtimestamp(self.test_metrics['start'])!s}
            **Test duration**: {datetime.timedelta(seconds=self.test_metrics['duration'])!s}
            **Test outcome**: {self.test_metrics['outcome']}
            """
        )

        if self.test_metrics.get("test:phase:exception"):
            overview += textwrap.dedent(
                f"""
                **Last successful test phase**: {self.test_metrics.get('test:phase:end')}
                **Failure in test phase**: {self.test_metrics['test:phase:exception']}
                """
            )

        return overview

    def build_contact_table(self) -> str | None:
        try:
            contacts = self.get_contacts()
            if contacts:
                primary_contact = contacts[0]
                name = primary_contact.get("name", "n/a")
                org = primary_contact.get("organization", "n/a")
                contact_info = primary_contact.get("contactInstructions", "")
                if primary_contact.get("links"):
                    links = [
                        f"[{link.get('title', 'link')}]({link.get('href', '#')})"
                        for link in primary_contact.get("links", [])
                    ]
                    contact_info += " (" + ", ".join(links) + ")"
                return textwrap.dedent(
                    f"""
                    | Name   | Organization | Contact |
                    |--------|--------------|---------|
                    | {name} | {org}        | {contact_info} |
                    """
                )
        except Exception as e:
            logger.error(
                f"Failed constructing contact table for scenario {self.scenario.id}: {e!r}"
            )

    def build_issue_body(self) -> str:
        body = self.build_workflow_run_overview()

        contact_table = self.build_contact_table()
        if contact_table:
            body += "\n\n### Contact Information\n\n" + contact_table

        process_graph = json.dumps(self.scenario.process_graph, indent=2)
        body += "\n\n### Process Graph"
        body += f"\n\n```json\n{process_graph}\n```"

        body += "\n\n### Error Logs"
        body += f"\n\n```plaintext\n{self.failure_logs}\n```\n"

        return body

    def build_comment_body(self) -> str:
        """Build the comment body for an existing issue"""
        return "Report of latest run:\n\n" + self.build_workflow_run_overview()


class GithubIssueHandler:
    def __init__(
        self,
        github_context: GithubContext | None = None,
        github_token: str | None = None,
        issue_label: str = "benchmark-failure",
    ):
        self.github_context = github_context or GithubContext()
        self.github_api = GithubApi(
            repository=self.github_context.repository,
            token=github_token or self.github_context.token,
        )
        self.issue_label = issue_label
        self._benchmark_scenarios = get_benchmark_scenarios()

    def get_benchmark_scenarios(self, scenario_id: str) -> BenchmarkScenario | None:
        matches = [s for s in self._benchmark_scenarios if s.id == scenario_id]
        if len(matches) == 1:
            return matches[0]
        elif len(matches) == 0:
            return None
        else:
            raise ValueError(
                f"Found {len(matches)} benchmark scenarios with {scenario_id=}"
            )

    def main(self) -> None:
        """
        Main flow: parse failed tests, check for existing issues, and create new issues as needed.
        """
        cli = argparse.ArgumentParser()
        cli.add_argument("--terminal-report", required=True, type=Path)
        cli.add_argument("--metrics-json", required=True, type=Path)
        cli_args = cli.parse_args()

        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )

        # Parse pytest reports
        pytest_report_parser = PytestReportParser()
        test_reports = pytest_report_parser.parse_metrics_json(cli_args.metrics_json)
        logger.info(
            f"Extracted {len(test_reports)} test reports from {cli_args.metrics_json}"
        )
        failure_logs = pytest_report_parser.extract_failure_logs(
            path=cli_args.terminal_report
        )
        logger.info(
            f"Extracted {len(failure_logs)} failure logs from {cli_args.terminal_report}"
        )

        # Collect existing GitHub issues
        all_existing_issues = self.github_api.list_issues(labels=[self.issue_label])
        logger.info(
            f"Found {len(all_existing_issues)} existing issues labeled '{self.issue_label}'"
        )

        for test_report in test_reports:
            logger.info(f"Handling {test_report=}")
            scenario_id = test_report.get("scenario_id")
            node_id = test_report.get("nodeid")
            outcome = test_report.get("outcome")
            failing_test = outcome == "failed"

            # Find benchmark scenario by ID
            benchmark_scenario = self.get_benchmark_scenarios(scenario_id)
            if not benchmark_scenario:
                # TODO: still possible to create issue/comment even without scenario details?
                logger.warning(f"Skipping {scenario_id=}: no benchmark scenario found")
                continue

            # Logs are organized based on the last part of the node_id
            logs = failure_logs.get(node_id.split("::")[-1])

            scenario_run_info = ScenarioRunInfo(
                scenario=benchmark_scenario,
                github_context=self.github_context,
                test_metrics=test_report,
                failure_logs=logs,
            )

            # Look for existing issues with the same title
            issue_title = scenario_run_info.issue_title()
            existing_issues = [
                i for i in all_existing_issues if i["title"] == issue_title
            ]

            if failing_test and not existing_issues:
                logger.info(
                    f"Creating new issue for newly failing scenario {scenario_id!r}"
                )
                self.github_api.create_issue(
                    title=issue_title,
                    body=scenario_run_info.build_issue_body(),
                    labels=[self.issue_label],
                )
            elif existing_issues:
                for issue in existing_issues:
                    issue_number = issue["number"]
                    logger.info(
                        f"Commenting on existing issue #{issue_number} for scenario {scenario_id!r}"
                    )
                    self.github_api.create_issue_comment(
                        issue_number=issue_number,
                        body=scenario_run_info.build_comment_body(),
                    )


if __name__ == "__main__":
    GithubIssueHandler().main()
