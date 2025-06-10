
import os
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
class FailureRecord:
    test_name: str
    scenario_id: str
    logs: str

# -----------------------------------------------------------------------------
# Issue Manager with pagination 
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
            f"{scenario['process_graph']}\n"
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
            f"## Benchmark {status}: {scenario.id}\n"
            f"**Scenario ID**: {scenario.id}\n"
            f"**Backend**: {scenario.backend}\n"
            f"**Timestamp**: {timestamp}\n\n"
            f"**Links**:\n"
            f"- Workflow Run: {self.workflow_run_url}\n"
            f"- Scenario Definition: {scenario.scenario_link}\n"
            f"- Artifacts: {self.workflow_run_url}#artifacts\n"
        )

    def create_issue(self, scenario: Scenario, logs: str) -> None:
        title = f"Scenario Failure: {scenario.id}"
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
        self.logger.warning("Scenario '%s' not found", scenario_id)
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
                    self.logger.error("Invalid JSON in %s: %s", rec, e)
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

    def parse_failures(self) -> List[FailureRecord]:
        text = Path("qa/benchmarks/pytest_output.txt")
        if not text.exists():
            self.logger.error("Log file not found: %s", text)
            return []
        content = text.read_text()
        pattern = r"=+ FAILURES =+.*?(test_run_benchmark\[(.*?)\]).*?\n(.*?)(?=\n=+|\Z)"
        records = []
        for m in __import__('re').finditer(pattern, content, __import__('re').DOTALL):
            records.append(FailureRecord(
                test_name=m.group(1),
                scenario_id=m.group(2),
                logs=m.group(3).strip()
            ))
        self.logger.info("Found %d failures", len(records))
        return records

# -----------------------------------------------------------------------------
# Unified Handler
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Benchmark failure/success handler")
    parser.add_argument("--mode", choices=["failure", "success"], required=True)

    GITHUB_REPO = "ESA-APEx/apex_algorithms"
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    if not GITHUB_TOKEN:
        raise EnvironmentError("GITHUB_TOKEN environment variable is not set.")
    args = parser.parse_args()


    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler()]
    )

    run_id = os.getenv("GITHUB_RUN_ID", "0")
    run_url = f"https://github.com/{GITHUB_REPO}/actions/runs/{run_id}"

    config = GitHubConfig(repo=GITHUB_REPO, token=GITHUB_TOKEN)
    manager = IssueManager(config, run_url)
    processor = ScenarioProcessor()

    existing = manager.get_existing_issues()
    failures = processor.parse_failures()

    for rec in failures:
        scen = processor.get_scenario_details(rec.scenario_id)
        if not scen:
            continue
        title = f"Scenario Failure: {rec.scenario_id}"
        if title not in existing:
            if args.mode == "failure":
                manager.create_issue(scen, rec.logs)
        else:
            num = existing[title].get("number")
            if not num:
                manager.logger.error("Issue without number: %s", title)
                continue
            if args.mode == "failure":
                body = manager.build_issue_body(scen, rec.logs)
            else:
                body = manager.build_comment_body(scen, success=True)
            manager.comment_issue(num, body)

if __name__ == "__main__":
    main()

