import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from apex_algorithm_qa_tools.scenarios import get_benchmark_scenarios, get_project_root

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class GitHubIssueManager:
    """
    Handles interactions with the GitHub API, including building the issue body
    and creating new issues.
    """

    def __init__(
        self,
        repository: Optional[str] = None,
        token: Optional[str] = None,
        issue_label: str = "benchmark-failure",
    ):
        self.repo = repository or os.getenv("GITHUB_REPOSITORY", "n/a")
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.issue_label = issue_label

    def _auth_header(self) -> str:
        assert self.token, "GitHub token is required"
        return f"Bearer {self.token}"

    def get_existing_issues(self) -> Dict[str, Any]:
        """
        Retrieve a mapping of existing open issue titles to issue details.
        """
        url = f"https://api.github.com/repos/{self.repo}/issues?state=open&labels={self.issue_label}"
        headers = {"Authorization": self._auth_header()}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            issues = response.json()
            return {
                issue["title"]: issue
                for issue in issues
                if issue.get("state") == "open"
            }
        except requests.RequestException as e:
            logger.error(
                "Failed to fetch issues: %s. Response: %s",
                e,
                getattr(response, "text", "No response"),
            )
            return {}

    def build_issue_body(
        self, scenario: Dict[str, Any], logs: str, failure_count: int
    ) -> str:
        """
        Build the GitHub issue body based on scenario details, logs, and contacts.
        """
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

        github_server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com")
        github_repository = os.getenv("GITHUB_REPOSITORY")
        github_run_id = os.getenv("GITHUB_RUN_ID")
        if github_repository and github_run_id:
            workflow_run_url = (
                f"{github_server_url}/{github_repository}/actions/runs/{github_run_id}"
            )
        else:
            workflow_run_url = "n/a"

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

    def create_issue(self, scenario: Dict[str, Any], logs: str) -> None:
        """
        Create a new GitHub issue for the given scenario failure.
        """
        issue_body = self.build_issue_body(scenario, logs, failure_count=1)
        url = f"https://api.github.com/repos/{self.repo}/issues"
        headers = {
            "Authorization": self._auth_header(),
            "Accept": "application/vnd.github.v3+json",
        }
        data = {
            "title": f"Scenario Failure: {scenario['id']}",
            "body": issue_body,
            "labels": [self.issue_label],
        }
        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            issue_url = response.json().get("html_url", "URL not available")
            logger.info("Created new issue: %s", issue_url)
        except requests.RequestException as e:
            logger.error(
                "Failed to create issue for scenario '%s': %s", scenario["id"], e
            )


class ScenarioProcessor:
    """
    Processes scenario details, including retrieving scenario data,
    contacts, and parsing the log file for failed tests.
    """

    def get_scenario_details(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve scenario details by ID.
        """
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

    def parse_failed_tests(self) -> List[Dict[str, str]]:
        """
        Parse the pytest output file to extract failed tests and logs.
        """
        log_file = Path("qa/benchmarks/pytest_output.txt")
        if not log_file.exists():
            logger.error("Pytest output file not found at %s", log_file)
            return []
        try:
            content = log_file.read_text()
            failures = []
            pattern = (
                r"=+ FAILURES =+\n.*?_* (test_run_benchmark\[(.*?)\])"
                r"(?:.*?)\n(.*?)(?=\n=+|\Z)"
            )
            matches = re.finditer(pattern, content, re.DOTALL)
            for match in matches:
                test_name = match.group(1)
                scenario_id = match.group(2)
                logs = match.group(3).strip()
                failures.append(
                    {"test_name": test_name, "scenario_id": scenario_id, "logs": logs}
                )
            logger.info("Found %d failed scenario(s)", len(failures))
            return failures
        except Exception as e:
            logger.error("Error parsing log file: %s", e)
            return []


def main() -> None:
    """
    Main flow: parse failed tests, check for existing issues, and create new issues as needed.
    """
    github_manager = GitHubIssueManager()
    scenario_processor = ScenarioProcessor()

    existing_issues = github_manager.get_existing_issues()
    failed_tests = scenario_processor.parse_failed_tests()

    for failure in failed_tests:
        scenario_id = failure["scenario_id"]
        logs = failure["logs"]

        scenario = scenario_processor.get_scenario_details(scenario_id)
        if not scenario:
            logger.warning("Skipping scenario '%s' - details not found", scenario_id)
            continue

        issue_title = f"Scenario Failure: {scenario_id}"
        if issue_title not in existing_issues:
            github_manager.create_issue(scenario, logs)
        else:
            logger.info(
                "Issue already exists for scenario '%s'. Skipping.", scenario_id
            )


if __name__ == "__main__":
    main()
