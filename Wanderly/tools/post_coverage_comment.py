import json
import os
import sys

import requests

# Load the GitHub Actions event data from disk
def loadEvent():
    # Path provided by GitHub
    event_path = os.environ.get("GITHUB_EVENT_PATH")

    # Exit if we cannot locate the payload
    if not event_path or not os.path.exists(event_path):
        print("No GitHub event payload found; skipping coverage comment.")
        sys.exit(0)

    # Open and parse the payload file
    with open(event_path, "r", encoding="utf-8") as f:
        return json.load(f)  # Return the JSON payload as a dictionary


# Read the coverage report from a file
def readReport(path: str) -> str:
    # Load the coverage report content
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
    
    # Handle missing file gracefully
    except FileNotFoundError:
        print(f"Coverage report {path} not found; skipping comment.")
        sys.exit(0)

    # Exit if the report is empty
    if (not content):
        print("Coverage report empty; skipping comment.")
        sys.exit(0)
    return content

# Build the Markdown comment body for the coverage report
def buildComment(report: str) -> str:
    header = "**Coverage Report**"      # Markdown header for emphasis
    body = f"```text\n{report}\n```"    # Preserve report formatting in a code block
    return f"{header}\n\n{body}"        # Combine header and body


# Post the coverage report comment to the pull request
def postComment(repo_full_name: str, pr_number: int, body: str) -> None:
    # Fetch GitHub token for authentication
    token = os.environ.get("GITHUB_TOKEN")

    # Exit if no token is available 
    if not token:
        print("GITHUB_TOKEN not set; cannot post coverage comment.")
        return

    # Construct the API request to post the comment
    url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"

    # Required headers for the API
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
    }

    # Send the POST request to create the comment
    response = requests.post(url, headers=headers, json={"body": body}, timeout=30)

    # Handle potential API errors
    if response.status_code >= 300:
        print(f"Failed to post coverage comment ({response.status_code}): {response.text}")
    else:
        print("Posted coverage report comment to PR.")


def main():
    # Determine the coverage report path
    if len(sys.argv) > 1:
        report_path = sys.argv[1]     # Respect custom report path
    else:
        report_path = "coverage.txt"  # Default coverage file name

    # Load GitHub event data
    event = loadEvent()

    # Ensure this is a pull request event
    if event.get("pull_request") is None:
        print("Not a pull request event; skipping coverage comment.")
        sys.exit(0)

    repo_full_name = event["repository"]["full_name"]  # Repo identifier for API call
    pr_number = event["pull_request"]["number"]        # PR number to comment on

    report = readReport(report_path)                 # Load coverage report text
    comment = buildComment(report)                   # Assemble final comment body
    postComment(repo_full_name, pr_number, comment)  # Send comment to GitHub


if __name__ == "__main__":
    main()  # Execute main routine when the script runs directly
