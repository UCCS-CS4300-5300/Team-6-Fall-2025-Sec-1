import json
import os
import sys

import requests


def load_event():
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        print("No GitHub event payload found; skipping coverage comment.")
        sys.exit(0)
    with open(event_path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_report(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except FileNotFoundError:
        print(f"Coverage report {path} not found; skipping comment.")
        sys.exit(0)

    if not content:
        print("Coverage report empty; skipping comment.")
        sys.exit(0)
    return content


def build_comment(report: str) -> str:
    header = "**Coverage Report**"
    body = f"```text\n{report}\n```"
    return f"{header}\n\n{body}"


def post_comment(repo_full_name: str, pr_number: int, body: str) -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN not set; cannot post coverage comment.")
        return

    url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
    }
    response = requests.post(url, headers=headers, json={"body": body}, timeout=30)
    if response.status_code >= 300:
        print(f"Failed to post coverage comment ({response.status_code}): {response.text}")
    else:
        print("Posted coverage report comment to PR.")


def main():
    if len(sys.argv) > 1:
        report_path = sys.argv[1]
    else:
        report_path = "coverage.txt"

    event = load_event()
    if event.get("pull_request") is None:
        print("Not a pull request event; skipping coverage comment.")
        sys.exit(0)

    repo_full_name = event["repository"]["full_name"]
    pr_number = event["pull_request"]["number"]

    report = read_report(report_path)
    comment = build_comment(report)
    post_comment(repo_full_name, pr_number, comment)


if __name__ == "__main__":
    main()
