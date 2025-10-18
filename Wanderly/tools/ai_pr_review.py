import json
import os
import subprocess
import sys

import openai
import requests


def load_event():
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        print("No GitHub event payload found; skipping AI review.")
        sys.exit(0)
    with open(event_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_diff(base_sha: str, head_sha: str) -> str:
    try:
        diff = subprocess.check_output(
            ["git", "diff", "--unified=3", f"{base_sha}", f"{head_sha}"],
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Unable to create diff: {exc}")
        sys.exit(1)

    if not diff.strip():
        print("No diff between base and head; skipping AI review.")
        sys.exit(0)

    max_length = 8000
    if len(diff) > max_length:
        diff = diff[:max_length] + "\n\n...diff truncated..."
    return diff


def fetch_pr_details(repo_full_name: str, pr_number: int) -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code != 200:
        print(f"Unable to fetch PR details ({response.status_code}): {response.text}")
        return {}
    return response.json()


def format_header(event: dict, pr_details: dict) -> None:
    pr = event["pull_request"]
    title = pr["title"]
    number = pr["number"]
    state = pr["state"].capitalize()
    user = pr["user"]["login"]
    base_branch = pr["base"]["ref"]
    head_branch = pr["head"]["ref"]
    repo_full_name = event["repository"]["full_name"]

    commits = pr_details.get("commits")
    additions = pr_details.get("additions")
    deletions = pr_details.get("deletions")
    changed_files = pr_details.get("changed_files")

    print(f"{title} #{number}")
    print(f"{state}")
    print(f"{user} wants to merge {commits or '?'} commit(s) into {base_branch} from {head_branch}")

    if additions is not None and deletions is not None:
        print(f"+{additions} −{deletions}")
    if changed_files is not None:
        print(f"Files changed {changed_files}")
    print()


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not set; skipping AI review.")
        sys.exit(0)

    event = load_event()
    if event.get("pull_request") is None:
        print("Not a pull request event; skipping AI review.")
        sys.exit(0)

    repo_full_name = event["repository"]["full_name"]
    pr_number = event["pull_request"]["number"]

    pr_details = fetch_pr_details(repo_full_name, pr_number)

    base_sha = event["pull_request"]["base"]["sha"]
    head_sha = event["pull_request"]["head"]["sha"]
    diff = build_diff(base_sha, head_sha)

    client = openai.OpenAI(api_key=api_key)
    prompt = (
        "You are reviewing a pull request for a Django project. "
        "Produce feedback in the following format:\n"
        "1. Begin with a single paragraph that starts with "
        "\"Based on the changes ... I'd give this code X out of 10\" "
        "where X is an integer rating between 1 and 10, and briefly justify the rating.\n"
        "2. Add a blank line.\n"
        "3. Provide 3-5 numbered sections, each on its own line, in the format "
        "\"1) Title Case Heading: detail(under the heading on a new line)\". Use Title Case for the heading, "
        "keep the detail concise, and leave a blank line between sections.\n"
        "4. Avoid Markdown headers (no # symbols) and keep the response easy to scan."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": diff},
            ],
            temperature=0.2,
        )
    except Exception as exc:
        print(f"OpenAI API call failed: {exc}")
        sys.exit(0)

    review_text = response.choices[0].message.content.strip()

    format_header(event, pr_details)
    print("AI Code Review")
    print(review_text)

    post_comment(repo_full_name, pr_number, format_comment(event, pr_details, review_text))


def format_comment(event: dict, pr_details: dict, review_text: str) -> str:
    pr = event["pull_request"]
    title = pr["title"]
    number = pr["number"]
    state = pr["state"].capitalize()
    user = pr["user"]["login"]
    base_branch = pr["base"]["ref"]
    head_branch = pr["head"]["ref"]

    commits = pr_details.get("commits")
    additions = pr_details.get("additions")
    deletions = pr_details.get("deletions")
    changed_files = pr_details.get("changed_files")

    return review_text


def post_comment(repo_full_name: str, pr_number: int, body: str) -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN not set; cannot post PR comment.")
        return

    url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
    }
    payload = {"body": body}

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code >= 300:
        print(f"Failed to post PR comment ({response.status_code}): {response.text}")
    else:
        print("Posted AI review comment to PR.")


if __name__ == "__main__":
    main()
