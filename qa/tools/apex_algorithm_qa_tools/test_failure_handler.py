
#%%
import os
import re
import requests
import json
from datetime import datetime
from pathlib import Path
import logging
from apex_algorithm_qa_tools.scenarios import get_benchmark_scenarios, get_project_root

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
GITHUB_REPO = "ESA-APEx/apex_algorithms"
GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN")
ISSUE_LABEL = "benchmark-failure"
SCENARIO_BASE_PATH = "qa/benchmarks/scenarios/"
WORKFLOW_BASE_URL = f"https://github.com/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}"

def get_existing_issues():
    """Fetch existing open issues and return them as {title: issue}"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues?state=open&labels={ISSUE_LABEL}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        open_issues = [issue for issue in response.json() if issue.get("state") == "open"]
        return {issue["title"]: issue for issue in open_issues}
    except Exception as e:
        logger.error(f"Failed to fetch issues: {str(e)} - Response: {response.text}")
        return {}

def get_scenario_details(scenario_id):
    """Retrieve details for a given scenario ID"""
    try:
        for scenario in get_benchmark_scenarios():
            if scenario.id == scenario_id:
                return {
                    "id": scenario.id,
                    "description": scenario.description,
                    "backend": scenario.backend,
                    "process_graph": json.dumps(scenario.process_graph, indent=2)
                }
        logger.warning(f"Scenario {scenario_id} not found")
        return None
    except ImportError:
        logger.error("Could not import scenario")
        return None
    except Exception as e:
        logger.error(f"Error loading scenarios: {str(e)}")
        return None
    
def get_scenario_contacts(scenario_id: str) -> list:
    """Find contact info by searching through algorithm catalog structure"""
    algorithm_catalog = get_project_root() / "algorithm_catalog"
    
    # Search through all provider directories
    for provider_dir in algorithm_catalog.iterdir():
        if not provider_dir.is_dir():
            continue
            
        # Check for matching algorithm directory
        algorithm_dir = provider_dir / scenario_id
        if not algorithm_dir.exists():
            continue
            
        # Look for records file
        records_path = algorithm_dir / "records" / f"{scenario_id}.json"
        if records_path.exists():
            try:
                with open(records_path) as f:
                    record = json.load(f)
                return record.get("properties", {}).get("contacts", [])
            except Exception as e:
                logger.error(f"Error loading contacts from {records_path}: {str(e)}")
                return []
    
    logger.warning(f"No contacts found for scenario {scenario_id}")
    return []

def get_scenario_link(scenario_id: str) -> str:
    """Generate link to process graph file at specific commit"""
    commit_sha = os.getenv("GITHUB_SHA", "main")  # Fallback to 'main' if not in CI
    base_url = f"https://github.com/{GITHUB_REPO}/blob/{commit_sha}"
    algorithm_catalog = get_project_root() / "algorithm_catalog"
    
    for provider_dir in algorithm_catalog.iterdir():
        if not provider_dir.is_dir():
            continue
        algorithm_dir = provider_dir / scenario_id
        if not algorithm_dir.exists():
            continue
        scenario_path = algorithm_dir / "benchmark_scenarios" / f"{scenario_id}.json"
        if scenario_path.exists():
            # Calculate the relative path from the project root.
            relative_path = scenario_path.relative_to(get_project_root())
            return f"{base_url}/{relative_path.as_posix()}"
    
    logger.warning(f"No benchmark found for scenario {scenario_id} on commit {base_url}") 
    return ""

    
def parse_failed_tests():
    """Parse pytest output to find failed scenarios and their logs"""
    log_file = Path("qa/benchmarks/pytest_output.txt")
    
    if not log_file.exists():
        logger.error("Pytest output file not found")
        return []

    try:
        content = log_file.read_text()
        failures = []
        
        # Match failed test entries with their logs
        pattern = r"=+ FAILURES =+\n.*?_* (test_run_benchmark\[(.*?)\])(?:.*?)\n(.*?)(?=\n=+|\Z)"

        matches = re.finditer(pattern, content, re.DOTALL)
        
        for match in matches:
            test_name = match.group(1)
            scenario_id = match.group(2)
            logs = match.group(3).strip()
            
            failures.append({
                "test_name": test_name,
                "scenario_id": scenario_id,
                "logs": logs
            })
        
        logger.info(f"Found {len(failures)} failed scenarios")
        return failures

    except Exception as e:
        logger.error(f"Error parsing log file: {str(e)}")
        return []


def build_issue_body(scenario, logs, failure_count):
    """Construct the issue body with technical details"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    contacts = get_scenario_contacts(scenario['id'])
    scenario_link = get_scenario_link(scenario['id'])
    
    contact_table = ""
    if contacts:
        try:
            contact_table = "\n\n**Point of Contact**:\n\n"
            contact_table += "| Name | Organization | Contact |\n"
            contact_table += "|------|--------------|---------|\n"
            # Extract links from contact instructions
            contact_info = contacts[0].get('contactInstructions', '')
            if contacts[0].get('links'):
                links = [f"[{link['title']}]({link['href']})" for link in contacts[0]['links']]
                contact_info += " (" + ", ".join(links) + ")"
            
            contact_table += (
                f"| {contacts[0].get('name', '')} "
                f"| {contacts[0].get('organization', '')} "
                f"| {contact_info} |\n"
            )
        except Exception as e:
            pass
    
    
    return f"""
## Benchmark Failure: {scenario['id']}

**Scenario ID**: {scenario['id']}
**Backend System**: {scenario['backend']}
**Failure Count**: {failure_count}
**Timestamp**: {timestamp}

**Links**:
- Workflow Run: {WORKFLOW_BASE_URL}
- Scenario Definition: {scenario_link}
- Artifacts: {WORKFLOW_BASE_URL}#artifacts

---
### Contact information
{contact_table}
---

### Process graph
```json
{scenario['process_graph']}
```

---
### Error Logs
```plaintext
{logs}
```
"""


    

def create_new_issue(scenario, logs):
    """Create a new GitHub issue"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    body = build_issue_body(scenario, logs, failure_count=1)
    
    data = {
        "title": f"Scenario Failure: {scenario['id']}",
        "body": body,
        "labels": [ISSUE_LABEL]
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        logger.info(f"Created new issue: {response.json()['html_url']}")
    except Exception as e:
        logger.error(f"Failed to create issue: {str(e)}")


def main():
    """Main processing flow"""
    existing_issues = get_existing_issues()
    failed_tests = parse_failed_tests()
    
    for failure in failed_tests:
        scenario_id = failure["scenario_id"]
        logs = failure["logs"]
        
        # Get scenario technical details
        scenario = get_scenario_details(scenario_id)
        if not scenario:
            logger.warning(f"Skipping {scenario_id} - details not found")
            continue
        
        issue_title = f"Scenario Failure: {scenario_id}"
        
        if issue_title not in existing_issues:
            create_new_issue(scenario, logs)

if __name__ == "__main__":
    main()


#%%
