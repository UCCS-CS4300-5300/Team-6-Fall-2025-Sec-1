import json  
import os  
import subprocess  
import sys  

import openai  
import requests

# Load the GitHub event payload from the environment
def loadEvent():

    # Grab the path to the GitHub event JSON from the environment
    event_path = os.environ.get("GITHUB_EVENT_PATH")

    # Exit if we cannot locate the payload
    if not event_path or not os.path.exists(event_path):
        print("No GitHub event payload found; skipping AI review.")
        sys.exit(0)

    # Open and parse the payload file
    with open(event_path, "r", encoding="utf-8") as f:
        return json.load(f)  # Convert the JSON payload into a Python dict


# Build the diff text between two commit SHAs
def buildDiff(base_sha: str, head_sha: str) -> str:
    # Generate a unified diff between the base and head commits
    try:
        diff = subprocess.check_output(
            ["git", "diff", "--unified=3", f"{base_sha}", f"{head_sha}"],
            text=True,
        )  # Capture the textual diff between the two SHAs

    except subprocess.CalledProcessError as exc:
        print(f"Unable to create diff: {exc}")
        sys.exit(1)

    # Exit if there is no diff to review
    if not diff.strip():
        print("No diff between base and head; skipping AI review.")
        sys.exit(0)

    # Limit how much diff we send to the API
    max_length = 8000

    # Truncate the diff if it exceeds the maximum length
    if len(diff) > max_length:
        diff = diff[:max_length] + "\n\n...diff truncated..."  # Prevent huge prompts
    return diff

# Retrieve pull-request metadata from the GitHub API
def fetchPRDetails(repo_full_name: str, pr_number: int) -> dict:

    # Retrieve pull-request metadata from the GitHub API
    token = os.environ.get("GITHUB_TOKEN")

    # Ask for JSON response
    headers = {"Accept": "application/vnd.github+json"}

    # Include authorization header if we have a token
    if token:
        headers["Authorization"] = f"Bearer {token}"                          # Authenticate when possible
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"  # Target PR endpoint
    response = requests.get(url, headers=headers, timeout=30)                 # Call GitHub API

    # Handle potential API errors
    if response.status_code != 200:
        print(f"Unable to fetch PR details ({response.status_code}): {response.text}")
        return {}
    return response.json()  # Return parsed PR details

# Print a summary header for the pull request
def formatHeader(event: dict, pr_details: dict) -> None:
    # Print a human-friendly summary of the pull request
    pr = event["pull_request"]                          # Pull request info from the event
    title = pr["title"]                                 # Title shown in the summary
    number = pr["number"]                               # PR number for reference
    state = pr["state"].capitalize()                    # State capitalized for presentation
    user = pr["user"]["login"]                          # PR author username
    base_branch = pr["base"]["ref"]                     # Target branch
    head_branch = pr["head"]["ref"]                     # Source branch
    repo_full_name = event["repository"]["full_name"]   # Repo identifier

    commits = pr_details.get("commits")                 # Number of commits in PR
    additions = pr_details.get("additions")             # Lines added
    deletions = pr_details.get("deletions")             # Lines removed
    changed_files = pr_details.get("changed_files")     # Files touched

    print(f"{title} #{number}")  # Print title and number
    print(f"{state}")            # Print PR state
    print(f"{user} wants to merge {commits or '?'} commit(s) into {base_branch} from {head_branch}")  # Print summary

    # Print stats if available
    if additions is not None and deletions is not None:
        print(f"+{additions} -{deletions}")     # Show additions and deletions
    if changed_files is not None:
        print(f"Files changed {changed_files}") # Show number of files changed
    print()  # Add space before review content


def formatComment(event: dict, pr_details: dict, review_text: str) -> str:
    # Return the final comment body to post back to the pull request
    pr = event["pull_request"]          # Unused but kept for future enhancement
    title = pr["title"]                 # Placeholder retrieving PR title
    number = pr["number"]               # Placeholder retrieving PR number
    state = pr["state"].capitalize()    # Placeholder retrieving PR state
    user = pr["user"]["login"]          # Placeholder retrieving PR author
    base_branch = pr["base"]["ref"]     # Placeholder retrieving base branch
    head_branch = pr["head"]["ref"]     # Placeholder retrieving head branch

    commits = pr_details.get("commits")              # Placeholder commits count
    additions = pr_details.get("additions")          # Placeholder additions count
    deletions = pr_details.get("deletions")          # Placeholder deletions count
    changed_files = pr_details.get("changed_files")  # Placeholder changed files count

    # Currently return the raw review text
    return review_text

# Send the AI review back to GitHub as a PR comment
def postComment(repo_full_name: str, pr_number: int, body: str) -> None:

    # Fetch GitHub token for authentication
    token = os.environ.get("GITHUB_TOKEN")
    
    # Exit if we cannot post the comment
    if not token:
        print("GITHUB_TOKEN not set; cannot post PR comment.")
        return
    
    # Get the comments endpoint for the PR
    url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"

    # Prepare headers and payload for the POST request
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
    }  # Include token in headers

    # Payload with comment body
    payload = {"body": body}

    # Post the comment to the PR
    response = requests.post(url, headers=headers, json=payload, timeout=30)

    # Handle potential API errors
    if response.status_code >= 300:
        print(f"Failed to post PR comment ({response.status_code}): {response.text}")
    else:
        print("Posted AI review comment to PR.")


def main():
    # Read OpenAI API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")

    # Exit if no API key is provided
    if not api_key:
        print("OPENAI_API_KEY not set; skipping AI review.")
        sys.exit(0)

    # Load GitHub event data
    event = loadEvent() 

    # Ensure this is a pull request event
    if event.get("pull_request") is None:
        print("Not a pull request event; skipping AI review.")
        sys.exit(0)

    repo_full_name = event["repository"]["full_name"]   # Repo identifier
    pr_number = event["pull_request"]["number"]         # Current PR number

    pr_details = fetchPRDetails(repo_full_name, pr_number)  # Fetch PR metadata

    base_sha = event["pull_request"]["base"]["sha"]  # Base commit SHA
    head_sha = event["pull_request"]["head"]["sha"]  # Head commit SHA

    # # Build diff text between base and head
    diff = buildDiff(base_sha, head_sha)

    # Initialize OpenAI client and prepare prompt
    client = openai.OpenAI(api_key=api_key)
    prompt = (
    "You are reviewing a pull request for a Django project.\n\n"
    "Context:\n"
    "- PR Title: {{pr_title}}\n"
    "- PR Description: {{pr_description}}\n"
    "- CI Status: {{ci_status}}\n"
    "- Files Changed (paths only): {{files_changed}}\n"
    "- Commit Messages (newest first): {{commit_messages}}\n"
    "- Unified Diff (git diff with context):\n{{diff}}\n\n"
    "Task:\n"
    "Write an evidence-based review focused on what changed in this PR and why it matters. "
    "Your output must follow the exact format below. Do not use Markdown headers (#). "
    "Do not invent files, symbols, or line numbers that are not present in the diff. "
    "If information is missing, explicitly say \"Not shown in diff.\"\n\n"
    "Format:\n"
    "1) Start with a single paragraph beginning with: "
    "\"Based on the changes ... I’d give this code X out of 10\" "
    "where X is an integer 1–10. In the same paragraph, briefly justify the score and "
    "list the top 2–4 drivers (e.g., test coverage, correctness, complexity, security, performance, style).\n\n"
    "2) Summary Of Changes\n"
    "Write 3–6 concise bullet points that summarize WHAT changed at a high level "
    "(features removed/added, key refactors, migrations, settings changes) using the diff and commit messages.\n\n"
    "3) What Changed, File By File\n"
    "Provide one or more lines, each like this:\n"
    "- path/to/file.py:lineStart-lineEnd — brief description of the change and WHY it was made. "
    "Only include ranges visible in the diff. Group related hunks if useful.\n\n"
    "4) Strengths\n"
    "List 2–6 bullets highlighting the best parts of the PR with specific references where possible.\n\n"
    "5) Issues And How To Fix Them\n"
    "Write short sections using this exact 2-line format with a blank line between sections:\n"
    "Title Case Heading\n"
    "detail explaining the issue, cite file paths and line ranges, and give a concrete fix suggestion.\n\n"
    "6) Test Recommendations\n"
    "Suggest 2–6 realistic tests based on this PR. Use this format for each bullet:\n"
    "- test_name — target (path/module) — scenario and expected result.\n"
    "If no tests are missing, say: \"No additional tests recommended based on the diff.\"\n\n"
    "7) Risk And Impact\n"
    "In 2–4 bullets, summarize deploy risks including migrations, settings changes, or backward compatibility concerns.\n\n"
    "8) Why Points Were Deducted\n"
    "List 1–5 bullets that clearly explain the score, with evidence from specific files/lines.\n\n"
    "9) Changelog Snippet\n"
    "Provide 2–5 clean bullets suitable for a CHANGELOG.\n\n"
    "Guidelines:\n"
    "- Prioritize correctness, security, and data integrity over style.\n"
    "- Reference specific files and line ranges from the diff.\n"
    "- If CI failed, include brief failure context if it relates to these changes.\n"
    "- For database writes across multiple tables, suggest django.db.transaction.atomic if missing.\n"
    "- Identify possible N+1 Django ORM issues and suggest select_related/prefetch_related.\n"
    "- Review for unsafe DEBUG, SECRET_KEY, CORS, or ALLOWED_HOSTS usage.\n"
    "- Review DRF serializers, permissions, and validation.\n"
    "- For migrations, warn about destructive or risky schema changes.\n"
    "- Keep the tone helpful and specific. Avoid vague feedback.\n"
)


    # Call OpenAI API to generate the review
    try:
        response = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": diff},
            ],
            temperature=0.2,
        )

    # Handle potential API errors
    except Exception as exc:
        print(f"OpenAI API call failed: {exc}")
        sys.exit(0)

    # Extract the review text from the API response
    review_text = response.choices[0].message.content.strip()

    formatHeader(event, pr_details)    # Print PR summary to console
    print("AI Code Review")             # Label the review section
    print(review_text)                  # Display the AI feedback

    # Post comment to GitHub
    postComment(repo_full_name, pr_number, formatComment(event, pr_details, review_text))


if __name__ == "__main__":
    main()  # Run the main workflow when executed directly
