# backend/app/github.py

import os
import requests
import logging

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def post_pr_comment(
    repo: str,
    pr_number: int,
    comment: str,
):
    """
    Post a comment on a GitHub Pull Request.
    repo: owner/repo
    pr_number: PR number
    """
    if not GITHUB_TOKEN:
        logger.warning("GitHub token not set, skipping PR comment")
        return

    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    payload = {"body": comment}

    resp = requests.post(url, json=payload, headers=headers)

    if resp.status_code >= 300:
        logger.error("Failed to post PR comment: %s", resp.text)
    else:
        logger.info("PR comment posted successfully")
