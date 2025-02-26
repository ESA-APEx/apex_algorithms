import os
import re
import requests

GITHUB_REPO = "ESA-APEx/apex_algorithms"
GITHUB_TOKEN = os.getenv("ISSUE_TOKEN")  # This will read the secret
ISSUE_LABEL = "test-failure"

def get_existing_issues():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        issues = response.json()
        return {issue["title"] for issue in issues}
    else:
        print(f"Failed to fetch issues: {response.status_code}")
        return {}

def create_issue(test_name, error_msg, file_name):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {
        "title": f"Test Failure: {test_name}",
        "body": f"Error Message: {error_msg}\nFile: {file_name}",
        "labels": [ISSUE_LABEL],
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 201:
        print(f"Issue created successfully: {response.json()['html_url']}")
    else:
        print(f"Failed to create issue: {response.status_code}, {response.text}")

def parse_failed_tests():
    with open("pytest_output.txt", "r") as f:
        log_data = f.read()

    print("Pytest Output:\n", log_data)  # Debugging output

    failed_tests = re.findall(r"FAILED (\S+)::(\S+) ", log_data)  

    print(f"Parsed Failed Tests: {failed_tests}")  # Debugging output

    return [(test_name, file_name) for file_name, test_name in failed_tests]


if __name__ == "__main__":
    existing_issues = get_existing_issues()
    failed_tests = parse_failed_tests()

    for test_name, file_name in failed_tests:
        if f"Test Failure: {test_name}" not in existing_issues:
            create_issue(test_name, "Test failed", file_name)
        else:
            print(f"Issue already exists for: {test_name}")