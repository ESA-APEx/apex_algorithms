from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
from apex_algorithm_qa_tools.scenarios import get_benchmark_scenarios, get_project_root

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
            f"Created new issue: {resp.get('number')=} {resp.get('title')=} {resp.get('url')=}"
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


class GitHubIssueManager:
    """
    Handles interactions with the GitHub API, including building the issue body
    and creating new issues.
    """

    # TODO: merge GitHubIssueManager and ScenarioProcessor?

    def __init__(
        self, repository: str, token: str = None, issue_label: str = "benchmark-failure"
    ):
        self._github_api = GithubApi(repository=repository, token=token)
        self.issue_label = issue_label

    def get_existing_issues(self) -> List[dict]:
        """
        Retrieve a mapping of existing open issue titles to issue details.
        """
        # TODO Overkill to do this in a separate method?
        issues = self._github_api.list_issues(labels=[self.issue_label])
        logger.info(
            f"Listed {len(issues)} existing issues (labeled '{self.issue_label}')"
        )
        return issues

    def get_workflow_run_url(self) -> str:
        # TODO: get this from report/metrics instead of environment variables?
        github_server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com")
        github_repository = os.getenv("GITHUB_REPOSITORY")
        github_run_id = os.getenv("GITHUB_RUN_ID")
        if github_repository and github_run_id:
            workflow_run_url = (
                f"{github_server_url}/{github_repository}/actions/runs/{github_run_id}"
            )
        else:
            workflow_run_url = "n/a"
        return workflow_run_url

    def build_issue_body(
        self, scenario: Dict[str, Any], logs: str, failure_count: int
    ) -> str:
        """
        Build the GitHub issue body based on scenario details, logs, and contacts.
        """
        # TODO use real templating system?
        # TODO: avoid current timestamp, get timestamp from pytest report
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        contacts = scenario.get("contacts", [])
        scenario_link = scenario.get("scenario_link", "")

        contact_table = ""
        if contacts:
            try:
                contact_table += "\n\n**Point of Contact**:\n\n"
                contact_table += "| Name | Organization | Contact |\n"
                contact_table += "|------|--------------|---------|\n"
                primary_contact = contacts[0]
                contact_info = primary_contact.get("contactInstructions", "")
                if primary_contact.get("links"):
                    links = [
                        f"[{link.get('title', 'link')}]({link.get('href', '#')})"
                        for link in primary_contact.get("links", [])
                    ]
                    contact_info += " (" + ", ".join(links) + ")"
                contact_table += (
                    f"| {primary_contact.get('name', '')} "
                    f"| {primary_contact.get('organization', '')} "
                    f"| {contact_info} |\n"
                )
            except Exception as e:
                logger.error(
                    "Error constructing contact table for scenario '%s': %s",
                    scenario["id"],
                    e,
                )

        workflow_run_url = self.get_workflow_run_url()

        body = (
            f"## Benchmark Failure: {scenario['id']}\n\n"
            f"**Scenario ID**: {scenario['id']}\n"
            f"**Backend System**: {scenario['backend']}\n"
            f"**Failure Count**: {failure_count}\n"
            f"**Timestamp**: {timestamp}\n\n"
            f"**Links**:\n"
            f"- Workflow Run: {workflow_run_url}\n"
            f"- Scenario Definition: {scenario_link}\n"
            f"- Artifacts: {workflow_run_url}#artifacts\n\n"
            "---\n"
            f"### Contact Information\n{contact_table}\n"
            "---\n\n"
            "### Process Graph\n"
            "```json\n"
            f"{scenario['process_graph']}\n"
            "```\n\n"
            "---\n"
            "### Error Logs\n"
            "```plaintext\n"
            f"{logs}\n"
            "```\n"
        )
        return body

    def create_issue(self, scenario: Dict[str, Any], logs: str) -> dict:
        """
        Create a new GitHub issue for the given scenario failure.
        """
        # TODO: overkill to do this in a separate method?
        return self._github_api.create_issue(
            title=f"Scenario Failure: {scenario['id']}",
            body=self.build_issue_body(scenario, logs, failure_count=1),
            labels=[self.issue_label],
        )

    def create_issue_comment(self, issue_number: int, text: str) -> dict:
        """
        Create a comment on an existing issue for the given scenario failure.
        """
        # TODO: overkill to do this in a separate method?
        return self._github_api.create_issue_comment(
            issue_number=issue_number, body=text
        )


@dataclasses.dataclass
class TerminalReportSection:
    title: Union[str, None]
    subnodes: List[Union[str, TerminalReportSection]]


class ScenarioProcessor:
    """
    Processes scenario details, including retrieving scenario data,
    contacts, and parsing the log file for failed tests.
    """

    def get_scenario_details(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve scenario details by ID.
        """
        # TODO: don't try-except this
        try:
            for scenario in get_benchmark_scenarios():
                if scenario.id == scenario_id:
                    details = {
                        "id": scenario.id,
                        "description": scenario.description,
                        "backend": scenario.backend,
                        "process_graph": json.dumps(scenario.process_graph, indent=2),
                    }
                    # Add contacts and scenario link using helper methods.
                    details["contacts"] = self.get_scenario_contacts(scenario_id)
                    details["scenario_link"] = self.get_scenario_link(scenario_id)
                    return details
            logger.warning("Scenario '%s' not found", scenario_id)
            return None
        except Exception as e:
            logger.error("Error loading scenarios: %s", e)
            return None

    def get_scenario_contacts(self, scenario_id: str) -> List[Any]:
        """
        Retrieve contact information for a scenario from the algorithm catalog.
        """
        # TODO: this looks like it can be simplified (single "exists" check or glob?)
        algorithm_catalog = get_project_root() / "algorithm_catalog"
        for provider_dir in algorithm_catalog.iterdir():
            if not provider_dir.is_dir():
                continue
            algorithm_dir = provider_dir / scenario_id
            if not algorithm_dir.exists():
                continue
            records_path = algorithm_dir / "records" / f"{scenario_id}.json"
            if records_path.exists():
                try:
                    with records_path.open() as f:
                        record = json.load(f)
                    return record.get("properties", {}).get("contacts", [])
                except Exception as e:
                    logger.error("Error loading contacts from %s: %s", records_path, e)
                    return []
        logger.warning("No contacts found for scenario '%s'", scenario_id)
        return []

    def get_scenario_link(self, scenario_id: str) -> str:
        """
        Generate a URL to the scenario definition file at the specific commit.
        """
        github_repository = os.getenv("GITHUB_REPOSITORY", "n/a")
        github_sha = os.getenv("GITHUB_SHA", "main")
        base_url = f"https://github.com/{github_repository}/blob/{github_sha}"
        algorithm_catalog = get_project_root() / "algorithm_catalog"
        # TODO: simplify this chain of exist checks?
        for provider_dir in algorithm_catalog.iterdir():
            if not provider_dir.is_dir():
                continue
            algorithm_dir = provider_dir / scenario_id
            if not algorithm_dir.exists():
                continue
            scenario_path = (
                algorithm_dir / "benchmark_scenarios" / f"{scenario_id}.json"
            )
            if scenario_path.exists():
                relative_path = scenario_path.relative_to(get_project_root())
                return f"{base_url}/{relative_path.as_posix()}"
        logger.warning("No benchmark found for scenario '%s'", scenario_id)
        return ""

    def parse_metrics_json(self, path: Path) -> Dict[str, Any]:
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
                current_section.subnodes.append(line.strip())

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


def main() -> None:
    """
    Main flow: parse failed tests, check for existing issues, and create new issues as needed.
    """
    # TODO: move this main to GitHubIssueManager/ScenarioProcessor
    cli = argparse.ArgumentParser()
    cli.add_argument("--terminal-report", required=True, type=Path)
    cli.add_argument("--metrics-json", required=True, type=Path)
    cli_args = cli.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    github_manager = GitHubIssueManager(
        repository=os.getenv("GITHUB_REPOSITORY", "n/a"),
        token=os.getenv("GITHUB_TOKEN", "n/a"),
    )
    scenario_processor = ScenarioProcessor()

    all_existing_issues = github_manager.get_existing_issues()

    failure_logs = scenario_processor.extract_failure_logs(
        path=cli_args.terminal_report
    )

    for test_report in scenario_processor.parse_metrics_json(cli_args.metrics_json):
        logger.info(f"Handling {test_report=}")
        scenario_id = test_report.get("scenario_id")
        node_id = test_report.get("nodeid")
        outcome = test_report.get("outcome")

        if outcome != "failed":
            # TODO #171 also handle passing tests
            continue

        logs = failure_logs.get(node_id.split("::")[-1])

        scenario = scenario_processor.get_scenario_details(scenario_id)
        if not scenario:
            # TODO: still possible to create issue/comment even without scenario details?
            logger.warning("Skipping scenario '%s' - details not found", scenario_id)
            continue

        # TODO: avoid duplicate logic to build title
        issue_title = f"Scenario Failure: {scenario_id}"

        existing_issues = [i for i in all_existing_issues if i["title"] == issue_title]

        if not existing_issues:
            logger.info(f"Creating new issue for scenario {scenario_id}")
            github_manager.create_issue(scenario, logs)
        else:
            for issue in existing_issues:
                logger.info(
                    f"Commenting on existing issue {issue['number']} for scenario {scenario_id}"
                )
                workflow_run_url = github_manager.get_workflow_run_url()
                github_manager.create_issue_comment(
                    issue_number=issue["number"],
                    text=f"Results of latest run {workflow_run_url}: {outcome=}",
                )


if __name__ == "__main__":
    main()
