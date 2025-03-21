
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
GITHUB_TOKEN = os.getenv("APEX_ISSUE_TOKEN")
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
    
    contact_table = ""
    if contacts:
        try:
            contact_table = "\n\n**Responsible Contacts**:\n\n"
            contact_table += "| Name | Organization | Contact |\n"
            contact_table += "|------|--------------|---------|\n"
            for contact in contacts:
                # Extract links from contact instructions
                contact_info = contact.get('contactInstructions', '')
                if contact.get('links'):
                    links = [f"[{link['title']}]({link['href']})" for link in contact['links']]
                    contact_info += " (" + ", ".join(links) + ")"
                
                contact_table += (
                    f"| {contact.get('name', '')} "
                    f"| {contact.get('organization', '')} "
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

**LINKS**:
- Workflow Run: {WORKFLOW_BASE_URL}
- Scenario Definition: {get_scenario_link(scenario['id'])}
- Artifacts: {WORKFLOW_BASE_URL}#artifacts

---
### Contact information
{contact_table}
---


### Technical Details

**PROCESS GRAPH:**
```json
{scenario['process_graph']}
```

**ERROR LOGS:**
```plaintext
{logs}
```
"""

def get_scenario_link(scenario_id):
    """Generate link to scenario source code"""
    return f"https://github.com/{GITHUB_REPO}/tree/main/{SCENARIO_BASE_PATH}{scenario_id}.py"

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

def update_existing_issue(issue, scenario, new_logs):
    """Update an existing issue with new failure information"""
    url = issue["url"]
    current_body = issue["body"]
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Extract current failure count
    count_match = re.search(r"Failure Count: (\d+)", current_body)
    failure_count = int(count_match.group(1)) + 1 if count_match else 1
    
    update_section = f"""
NEW FAILURE OCCURRENCE

**Timestamp**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Workflow Run**: {WORKFLOW_BASE_URL}

**Error Logs**:
```plaintext
{new_logs}
```"""
    
    updated_body = f"{current_body}\n\n{update_section}"
    updated_body = re.sub(r"Failure Count: \d+", f"Failure Count: {failure_count}", updated_body)
    
    try:
        response = requests.patch(url, json={"body": updated_body}, headers=headers)
        response.raise_for_status()
        logger.info(f"Updated issue #{issue['number']}")
    except Exception as e:
        logger.error(f"Failed to update issue: {str(e)}")

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
        
        if issue_title in existing_issues:
            update_existing_issue(existing_issues[issue_title], scenario, logs)
        else:
            create_new_issue(scenario, logs)

if __name__ == "__main__":
    main()


#%%
