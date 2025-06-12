
import os
import re
import json
import logging
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import requests
from apex_algorithm_qa_tools.scenarios import get_benchmark_scenarios, get_project_root

# -----------------------------------------------------------------------------
# Configuration dataclass
# -----------------------------------------------------------------------------
@dataclass
class GitHubConfig:
    repo: str
    token: str
    label: str = "benchmark-failure"
    page_size: int = 100

# -----------------------------------------------------------------------------
# Issue and Scenario Data Models
# -----------------------------------------------------------------------------
@dataclass
class Scenario:
    id: str
    description: str
    backend: str
    process_graph: str
    contacts: List[Dict[str, Any]]
    scenario_link: str

@dataclass
class TestRecord:
    scenario_id: str
    status: str  # 'PASSED' or 'FAILED'
    logs: Optional[str] = None

# -----------------------------------------------------------------------------
# Issue Manager
# -----------------------------------------------------------------------------
class IssueManager:
    def __init__(self, config: GitHubConfig, workflow_run_url: str):
        self.config = config
        self.headers = {
            "Authorization": f"Bearer {config.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_issues_url = f"https://api.github.com/repos/{config.repo}/issues"
        self.workflow_run_url = workflow_run_url
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_existing_issues(self) -> Dict[str, Any]:
        """
        Retrieve all open issues with the given label, handling pagination.
        """
        page = 1
        existing = {}
        while True:
            params = {"state": "open", "labels": self.config.label, "per_page": self.config.page_size, "page": page}
            resp = requests.get(self.base_issues_url, headers=self.headers, params=params)
            resp.raise_for_status()
            issues = resp.json()
            if not issues:
                break
            for issue in issues:
                title = issue.get("title")
                if title:
                    existing[title] = issue
            page += 1
        self.logger.info("Fetched %d open issues", len(existing))
        return existing

    def build_issue_body(self, scenario: Scenario, logs: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        contact_entries = []
        if scenario.contacts:
            primary = scenario.contacts[0]
            name = primary.get("name", "")
            org = primary.get("organization", "")
            instr = primary.get("contactInstructions", "")
            links = primary.get("links", [])
            if links:
                link_strs = [f"[{l.get('title','link')}]({l.get('href','#')})" for l in links]
                instr += " (" + ", ".join(link_strs) + ")"
            contact_entries.append(f"| {name} | {org} | {instr} |")

        contact_table = (
            "\n**Point of Contact**:\n\n"
            "| Name | Organization | Contact |\n"
            "|------|--------------|---------|\n"
            + "\n".join(contact_entries)
            if contact_entries else ""
        )

        body = (
            f"## Benchmark Failure: {scenario.id}\n\n"
            f"**Scenario ID**: {scenario.id}\n"
            f"**Backend**: {scenario.backend}\n"
            f"**Timestamp**: {timestamp}\n\n"
            f"**Links**:\n"
            f"- Workflow Run: {self.workflow_run_url}\n"
            f"- Scenario Definition: {scenario.scenario_link}\n"
            f"- Artifacts: {self.workflow_run_url}#artifacts\n\n"
            "---\n"
            f"### Contact Information{contact_table}\n"
            "---\n\n"
            "### Process Graph\n"
            "```json\n"
            f"{scenario.process_graph}\n"
            "```\n\n"
            "---\n"
            "### Error Logs\n"
            "```plaintext\n"
            f"{logs}\n"
            "```\n"
        )
        return body

    def build_comment_body(self, scenario: Scenario, success: bool) -> str:
        status = "Success" if success else "Failure"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return (
            f"## Status: {status}\n"
            f"## Benchmark: {scenario.id}\n"
            f"**Scenario ID**: {scenario.id}\n"
            f"**Backend**: {scenario.backend}\n"
            f"**Timestamp**: {timestamp}\n\n"
            f"**Links**:\n"
            f"- Workflow Run: {self.workflow_run_url}\n"
            f"- Scenario Definition: {scenario.scenario_link}\n"
            f"- Artifacts: {self.workflow_run_url}#artifacts\n"
        )

    def create_issue(self, scenario: Scenario, logs: str) -> None:
        title = f"Benchmark Failure: {scenario.id}"
        body = self.build_issue_body(scenario, logs)
        payload = {"title": title, "body": body, "labels": [self.config.label]}
        resp = requests.post(self.base_issues_url, headers=self.headers, json=payload)
        resp.raise_for_status()
        url = resp.json().get("html_url")
        self.logger.info("Created issue %s", url)

    def comment_issue(self, issue_number: int, body: str) -> None:
        url = f"{self.base_issues_url}/{issue_number}/comments"
        resp = requests.post(url, headers=self.headers, json={"body": body})
        resp.raise_for_status()
        self.logger.info("Commented on issue #%d", issue_number)

    def close_issue(self, issue_number: int) -> None:
        url = f"{self.base_issues_url}/{issue_number}"
        resp = requests.patch(url, headers=self.headers, json={"state": "closed"})
        resp.raise_for_status()
        self.logger.info("Closed issue #%d", issue_number)

# -----------------------------------------------------------------------------
# Scenario Processor 
# -----------------------------------------------------------------------------
class ScenarioProcessor:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_scenario_details(self, scenario_id: str) -> Optional[Scenario]:

        for sc in get_benchmark_scenarios():
            if sc.id == scenario_id:
                details = Scenario(
                    id=sc.id,
                    description=sc.description,
                    backend=sc.backend,
                    process_graph=json.dumps(sc.process_graph, indent=2),
                    contacts=self._load_contacts(scenario_id),
                    scenario_link=self._build_scenario_link(scenario_id),
                )
                return details
        self.logger.info("Scenario '%s' not found", scenario_id)
        return None

    def _load_contacts(self, scenario_id: str) -> List[Any]:
        root = get_project_root() / "algorithm_catalog"
        for provider in root.iterdir():
            rec = provider / scenario_id / "records" / f"{scenario_id}.json"
            if rec.exists():
                try:
                    data = json.loads(rec.read_text())
                    return data.get("properties", {}).get("contacts", [])
                except json.JSONDecodeError as e:
                    self.logger.info("Invalid JSON in %s: %s", rec, e)
        self.logger.info("No contacts for '%s'", scenario_id)
        return []

    def _build_scenario_link(self, scenario_id: str) -> str:
        sha = os.getenv("GITHUB_SHA", "main")
        base = f"https://github.com/{os.getenv('GITHUB_REPO')}/blob/{sha}"
        root = get_project_root() / "algorithm_catalog"
        for provider in root.iterdir():
            path = provider / scenario_id / "benchmark_scenarios" / f"{scenario_id}.json"
            if path.exists():
                rel = path.relative_to(get_project_root())
                return f"{base}/{rel.as_posix()}"
        self.logger.info("No scenario definition for '%s'", scenario_id)
        return ""

    def parse_results(self) -> List[TestRecord]:
        text_path = Path("qa/benchmarks/pytest_output.txt")
        if not text_path.exists():
            self.logger.info("Log file not found: %s", text_path)
            return []
        content = text_path.read_text()
        records: List[TestRecord] = []
        # capture individual test outcomes
        for match in re.finditer(r"(test_run_benchmark\[(.*?)\]).*?\s(PASSED|FAILED)", content):
            test_name = match.group(1)
            scenario_id = match.group(2)
            status = match.group(3)
            logs = None
            if status == 'FAILED':
                # grab failure block
                fail_block = re.search(
                    rf"=+ FAILURES =+.*?{re.escape(test_name)}.*?\n(.*?)(?=\n=+|\Z)",
                    content, re.DOTALL
                )
                if fail_block:
                    logs = fail_block.group(1).strip()
            records.append(TestRecord(scenario_id=scenario_id, status=status, logs=logs))
        return records

# -----------------------------------------------------------------------------
# Unified Handler
# -----------------------------------------------------------------------------
def main():

    repo = os.getenv("GITHUB_REPO", "ESA-APEx/apex_algorithms")
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise EnvironmentError("GITHUB_TOKEN not set.")

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")

    run_id = os.getenv("GITHUB_RUN_ID", "0")
    workflow_url = f"https://github.com/{repo}/actions/runs/{run_id}"

    config = GitHubConfig(repo=repo, token=token)
    manager = IssueManager(config, workflow_url)
    processor = ScenarioProcessor()

    # parse all test results
    results = processor.parse_results()
    open_issues = manager.get_existing_issues()

    # handle each result
    for rec in results:
        title = f"Benchmark Failure: {rec.scenario_id}" #TODO loosely coupled with create_issue; tighten to avoid bugs
        scen = processor.get_scenario_details(rec.scenario_id)
        if not scen:
            continue
        if rec.status == 'FAILED':
            if title in open_issues:
                num = open_issues[title]['number']
                manager.comment_issue(num, manager.build_comment_body(scen, success=False))
            else:
                manager.create_issue(scen, rec.logs or "No logs captured.")
        else:  # PASSED
            if title in open_issues:
                num = open_issues[title]['number']
                manager.comment_issue(num, manager.build_comment_body(scen, success=True))
                manager.close_issue(num)

if __name__ == "__main__":
    main()

