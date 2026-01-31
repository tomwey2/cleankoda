"""Service for GitHub Pull Request operations."""

import logging
import os
import re
import subprocess
import json
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests

from app.agent.utils import CODE_DIR_NAME, get_codespace, get_current_git_branch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PullRequest:  # pylint: disable=too-many-instance-attributes
    """Represents a GitHub Pull Request."""

    number: int
    title: str
    body: str
    html_url: str
    state: str
    head_branch: str
    base_branch: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class GitHubContext:
    """Holds repository metadata required for PR operations."""

    owner: str
    repo: str
    branch: str
    headers: Dict[str, str]


@dataclass(frozen=True)
class PRReview:
    """Represents a GitHub Pull Request review."""

    id: str
    reviewer: str
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED
    body: str
    submitted_at: str


@dataclass(frozen=True)
class LineRange:
    """Represents a line range in a file."""

    start: Optional[int]
    end: Optional[int]


@dataclass(frozen=True)
class PRReviewComment:
    """Represents a line-level code review comment on a PR."""

    id: str
    reviewer: str
    body: str
    path: Optional[str]
    line_range: LineRange
    created_at: str
    is_resolved: bool = False


def get_latest_open_pr_for_branch(branch_name: str) -> Optional[PullRequest]:
    """
    Get the latest open pull request for the given branch.

    Args:
        branch_name: The name of the branch to check

    Returns:
        PullRequest object if an open PR exists, None otherwise
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("GITHUB_TOKEN not set, cannot fetch PR")
        return None

    try:
        owner, repo = get_github_repo_info()
        if not owner or not repo:
            logger.warning("Could not determine GitHub owner/repo")
            return None

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        params = {"head": f"{owner}:{branch_name}", "state": "open"}

        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            pulls = response.json()
            if pulls:
                pr_data = pulls[0]
                pr = PullRequest(
                    number=pr_data["number"],
                    title=pr_data["title"],
                    body=pr_data.get("body", ""),
                    html_url=pr_data["html_url"],
                    state=pr_data["state"],
                    head_branch=pr_data["head"]["ref"],
                    base_branch=pr_data["base"]["ref"],
                    created_at=pr_data["created_at"],
                    updated_at=pr_data["updated_at"],
                )
                logger.info(
                    "Found PR #%d for branch '%s': %s",
                    pr.number,
                    branch_name,
                    pr.title
                )
                return pr

            logger.info("No open PR found for branch '%s'", branch_name)
            return None

        logger.warning(
            "PR fetch failed with status %d: %s",
            response.status_code,
            response.text
        )
        return None

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error fetching PR for branch '%s': %s", branch_name, e)
        return None


def check_pr_exists_for_branch(branch_name: str) -> bool:
    """
    Check if a pull request exists for the given branch.

    Args:
        branch_name: The name of the branch to check

    Returns:
        True if a PR exists for this branch, False otherwise
    """
    return get_latest_open_pr_for_branch(branch_name) is not None


def create_or_update_pr(title: str, body: str) -> tuple[bool, str, Optional[str]]:
    """
    Creates or updates a GitHub Pull Request.

    Args:
        title: PR title
        body: PR body/description

    Returns:
        Tuple of (success, message, pr_url)
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.error("GITHUB_TOKEN missing for PR creation")
        return False, "ERROR: GITHUB_TOKEN missing", None

    try:
        context = build_github_context(token)
        if not context:
            return False, "ERROR: Missing GitHub context", None

        if context.branch in ["main", "master"]:
            return (
                False,
                "ERROR: You are on main/master. Create a feature branch first!",
                None,
            )

        url = f"https://api.github.com/repos/{context.owner}/{context.repo}/pulls"
        params = {"head": f"{context.owner}:{context.branch}", "state": "open"}
        response = requests.get(url, headers=context.headers, params=params, timeout=10)

        if response.status_code == 200:
            pulls = response.json()
            if pulls:
                return update_existing_pr(context, pulls[0], body)

        return create_new_pr(context, title, body)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("PR creation failed: %s", str(e))
        return False, f"ERROR: {str(e)}", None


def update_existing_pr(
    context: GitHubContext,
    pr_data: dict,
    body: str,
) -> tuple[bool, str, Optional[str]]:
    """
    Add comment to existing PR.

    Args:
        context: GitHub context with auth headers
        pr_data: Existing PR data from API
        body: Comment body to add

    Returns:
        Tuple of (success, message, pr_url)
    """
    pr_number = pr_data.get("number")
    pr_url = pr_data.get("html_url")
    comment_url = (
        f"https://api.github.com/repos/{context.owner}/{context.repo}/issues/"
        f"{pr_number}/comments"
    )
    comment_payload = {"body": f"**Automated Update:**\n\n{body}"}

    response = requests.post(
        comment_url,
        json=comment_payload,
        headers=context.headers,
        timeout=10,
    )

    if response.status_code == 201:
        logger.info("Added comment to existing PR: %s", pr_url)
        return True, f"SUCCESS: Added comment to existing PR: {pr_url}", pr_url
    return False, f"ERROR adding comment: {response.status_code}", pr_url


def create_new_pr(
    context: GitHubContext,
    title: str,
    body: str,
) -> tuple[bool, str, Optional[str]]:
    """
    Create new PR.

    Args:
        context: GitHub context with auth headers
        title: PR title
        body: PR description

    Returns:
        Tuple of (success, message, pr_url)
    """
    url = f"https://api.github.com/repos/{context.owner}/{context.repo}/pulls"
    payload = {"title": title, "body": body, "head": context.branch, "base": "main"}
    response = requests.post(url, json=payload, headers=context.headers, timeout=10)

    if response.status_code == 422:
        logger.info("Target 'main' not found, trying 'master'...")
        payload["base"] = "master"
        response = requests.post(url, json=payload, headers=context.headers, timeout=10)

    if response.status_code == 201:
        pr_url = response.json().get("html_url")
        logger.info("Pull Request created: %s", pr_url)
        return True, f"SUCCESS: Pull Request created: {pr_url}", pr_url

    return False, f"ERROR creating PR: {response.status_code} - {response.text}", None


def build_github_context(token: str) -> Optional[GitHubContext]:
    """
    Assemble the metadata required to interact with the GitHub API.

    Args:
        token: GitHub API token

    Returns:
        GitHubContext if successful, None otherwise
    """
    owner, repo, current_branch = get_github_repo_info_with_branch()
    if not owner or not repo or not current_branch:
        logger.error("Could not parse GitHub repository information")
        return None

    headers: Dict[str, str] = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    return GitHubContext(
        owner=owner,
        repo=repo,
        branch=current_branch,
        headers=headers,
    )


def get_github_repo_info() -> tuple[Optional[str], Optional[str]]:
    """
    Get GitHub owner and repo from git remote.

    Returns:
        Tuple of (owner, repo)
    """
    try:
        remote_url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=get_codespace(),
            text=True,
        ).strip()

        match = re.search(r"github\.com[:/](.+)/(.+?)(\.git)?$", remote_url)
        if not match:
            return None, None

        owner, repo = match.group(1), match.group(2)
        return owner, repo
    except subprocess.CalledProcessError:
        return None, None


def get_github_repo_info_with_branch() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Get GitHub owner, repo, and current branch.

    Returns:
        Tuple of (owner, repo, branch)
    """
    try:
        remote_url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=get_codespace(),
            text=True,
        ).strip()

        match = re.search(r"github\.com[:/](.+)/(.+?)(\.git)?$", remote_url)
        if not match:
            return None, None, None

        owner, repo = match.group(1), match.group(2)
        current_branch = get_current_git_branch()

        if not current_branch:
            return None, None, None

        return owner, repo, current_branch
    except subprocess.CalledProcessError:
        return None, None, None


def fetch_pr_reviews(
    pr_number: int,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    token: Optional[str] = None,
) -> List[PRReview]:
    """
    Fetch all reviews for a pull request.

    Args:
        pr_number: The PR number to fetch reviews for
        owner: Repository owner (optional, derived from git if not provided)
        repo: Repository name (optional, derived from git if not provided)
        token: GitHub token (optional, uses GITHUB_TOKEN env var if not provided)

    Returns:
        List of PRReview objects
    """
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("GITHUB_TOKEN not set, cannot fetch PR reviews")
        return []

    try:
        if not owner or not repo:
            owner, repo = get_github_repo_info()
        if not owner or not repo:
            logger.warning("Could not determine GitHub owner/repo")
            return []

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            reviews_data = response.json()
            reviews = [
                PRReview(
                    id=str(r["id"]),
                    reviewer=r.get("user", {}).get("login", "unknown"),
                    state=r.get("state", ""),
                    body=r.get("body", "") or "",
                    submitted_at=r.get("submitted_at", ""),
                )
                for r in reviews_data
            ]
            logger.info("Fetched %d reviews for PR #%d", len(reviews), pr_number)
            return reviews

        logger.warning(
            "PR reviews fetch failed with status %d: %s",
            response.status_code,
            response.text,
        )
        return []

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error fetching PR reviews for #%d: %s", pr_number, e)
        return []


def fetch_pr_review_comments(
    pr_number: int,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    token: Optional[str] = None,
    only_unresolved: bool = True,
) -> List[PRReviewComment]:
    """
    Fetch line-level code review comments for a pull request using GraphQL API.

    Args:
        pr_number: The PR number to fetch comments for
        owner: Repository owner (optional, derived from git if not provided)
        repo: Repository name (optional, derived from git if not provided)
        token: GitHub token (optional, uses GITHUB_TOKEN env var if not provided)
        only_unresolved: If True, only return unresolved comments (default: True)

    Returns:
        List of PRReviewComment objects
    """
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("GITHUB_TOKEN not set, cannot fetch PR review comments")
        return []

    if not owner or not repo:
        owner, repo = get_github_repo_info()
    if not owner or not repo:
        logger.warning("Could not determine GitHub owner/repo")
        return []

    try:
        comments = _fetch_pr_comments_via_graphql(
            owner, repo, pr_number, token, only_unresolved
        )
        logger.info(
            "Fetched %d %sreview comments for PR #%d",
            len(comments),
            "unresolved " if only_unresolved else "",
            pr_number,
        )
        return comments
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error fetching PR review comments for #%d: %s", pr_number, e)
        return []


def get_latest_pr_review_status(
    pr_number: int,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    token: Optional[str] = None,
) -> tuple[bool, List[PRReview], List[PRReviewComment]]:
    """
    Get the latest review status for a pull request.

    Fetches reviews and comments, determines if the PR is approved based on
    the latest review from each reviewer.

    Args:
        pr_number: The PR number to check
        owner: Repository owner (optional, derived from git if not provided)
        repo: Repository name (optional, derived from git if not provided)
        token: GitHub token (optional, uses GITHUB_TOKEN env var if not provided)

    Returns:
        Tuple of (is_approved, rejection_reviews, code_comments)
        - is_approved: True if the latest review state is APPROVED
        - rejection_reviews: List of reviews with CHANGES_REQUESTED state
        - code_comments: List of line-level code review comments
    """
    reviews = fetch_pr_reviews(pr_number, owner, repo, token)
    comments = fetch_pr_review_comments(pr_number, owner, repo, token)

    if not reviews:
        return True, [], comments

    latest_reviews_by_user: Dict[str, PRReview] = {}
    for review in reviews:
        if review.state in ("APPROVED", "CHANGES_REQUESTED"):
            existing = latest_reviews_by_user.get(review.reviewer)
            if not existing or review.submitted_at > existing.submitted_at:
                latest_reviews_by_user[review.reviewer] = review

    rejection_reviews = [
        r for r in latest_reviews_by_user.values() if r.state == "CHANGES_REQUESTED"
    ]

    is_approved = len(rejection_reviews) == 0 and any(
        r.state == "APPROVED" for r in latest_reviews_by_user.values()
    )

    logger.info(
        "PR #%d review status: approved=%s, rejections=%d, comments=%d",
        pr_number,
        is_approved,
        len(rejection_reviews),
        len(comments),
    )

    return is_approved, rejection_reviews, comments


def fetch_pr_details(
    owner: str,
    repo: str,
    pr_number: int,
    token: Optional[str] = None,
) -> Optional[PullRequest]:
    """
    Fetch basic PR details from GitHub.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: The PR number to fetch
        token: GitHub token (optional, uses GITHUB_TOKEN env var if not provided)

    Returns:
        PullRequest object or None if not found
    """
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("GITHUB_TOKEN not set, cannot fetch PR details")
        return None

    try:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return PullRequest(
                number=data["number"],
                title=data.get("title", ""),
                body=data.get("body", "") or "",
                html_url=data.get("html_url", ""),
                state=data.get("state", ""),
                head_branch=data.get("head", {}).get("ref", ""),
                base_branch=data.get("base", {}).get("ref", ""),
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
            )

        logger.warning(
            "PR fetch failed with status %d: %s",
            response.status_code,
            response.text,
        )
        return None

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error fetching PR #%d: %s", pr_number, e)
        return None


def format_pr_review_message(
    pr_url: str,
    rejection_reviews: List[PRReview],
    code_comments: List[PRReviewComment],
) -> str:
    """
    Format PR review feedback as a human-readable message.

    Args:
        pr_url: URL of the pull request
        rejection_reviews: List of reviews with CHANGES_REQUESTED state
        code_comments: List of line-level code review comments

    Returns:
        Formatted string for display
    """
    lines = [
        "",
        "=" * 60,
        "PULL REQUEST REVIEW FEEDBACK",
        "=" * 60,
        f"PR: {pr_url}",
        "",
    ]

    def _format_multiline(label: str, text: str) -> List[str]:
        if not text:
            return []
        split_lines = text.splitlines() or [""]
        formatted = [f"{label}{split_lines[0]}"]
        formatted.extend(f"{' ' * len(label)}{line}" for line in split_lines[1:])
        return formatted

    def _format_location(comment: PRReviewComment) -> str:
        start = comment.line_range.start
        end = comment.line_range.end

        if comment.path:
            if start and end and start != end:
                line_desc = f"{start}-{end}"
            elif start:
                line_desc = f"{start}"
            else:
                line_desc = "?"
            return f"{comment.path}:{line_desc}"

        if start and end:
            if start == end:
                return f"Line {start}"
            return f"Lines {start}-{end}"
        if start:
            return f"Line {start}"
        return "General"

    if rejection_reviews:
        latest = rejection_reviews[-1]
        lines.extend(
            [
                f"Review Status: {latest.state}",
                f"Reviewer: {latest.reviewer}",
                f"Date: {latest.submitted_at}",
                "",
            ]
        )
        lines.extend(_format_multiline("Review Comment: ", latest.body))
        if latest.body:
            lines.append("")

    if code_comments:
        lines.extend(
            [
                "-" * 40,
                "CODE REVIEW COMMENTS:",
                "-" * 40,
            ]
        )
        for comment in code_comments:
            location = _format_location(comment)
            lines.append(f"Location: {location} (by {comment.reviewer})")
            body_lines = _format_multiline("  ", comment.body)
            lines.extend(body_lines or ["  "])
            lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def _parse_review_comment(comment: dict, is_resolved: bool) -> PRReviewComment:
    """Parse a single review comment from GraphQL response."""
    return PRReviewComment(
        id=comment.get("id", ""),
        reviewer=comment.get("author", {}).get("login", "unknown"),
        body=comment.get("body", "") or "",
        path=f"{CODE_DIR_NAME}/{comment['path']}" if comment.get("path") else None,
        line_range=LineRange(
            start=comment.get("startLine"),
            end=comment.get("line"),
        ),
        created_at=comment.get("createdAt", ""),
        is_resolved=is_resolved,
    )


def _get_pr_review_comments_graphql_query() -> str:
    """Return the GraphQL query for fetching PR review comments."""
    return """
    query($owner: String!, $repo: String!, $prNumber: Int!) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $prNumber) {
          reviewThreads(first: 100) {
            nodes {
              isResolved
              comments(first: 100) {
                nodes {
                  id
                  body
                  path
                  line
                  startLine
                  createdAt
                  author {
                    login
                  }
                }
              }
            }
          }
        }
      }
    }
    """


def _extract_comments_from_threads(
    review_threads: List[dict], only_unresolved: bool
) -> List[PRReviewComment]:
    """Extract comments from review threads, optionally filtering by resolution status."""
    comments = []
    for thread in review_threads:
        is_resolved = thread.get("isResolved", False)
        if only_unresolved and is_resolved:
            continue

        thread_comments = thread.get("comments", {}).get("nodes", [])
        for comment in thread_comments:
            comments.append(_parse_review_comment(comment, is_resolved))
    return comments


def _fetch_pr_comments_via_graphql(
    owner: str, repo: str, pr_number: int, token: str, only_unresolved: bool
) -> List[PRReviewComment]:
    """Execute GraphQL query and parse response for PR review comments."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        "https://api.github.com/graphql",
        headers=headers,
        json={
            "query": _get_pr_review_comments_graphql_query(),
            "variables": {"owner": owner, "repo": repo, "prNumber": pr_number},
        },
        timeout=10,
    )

    if response.status_code != 200:
        logger.warning(
            "PR review comments fetch failed with status %d: %s",
            response.status_code,
            response.text,
        )
        return []

    data = response.json()
    logger.info("GraphQL response: %s", json.dumps(data, indent=2))

    if "errors" in data:
        logger.error("GraphQL errors: %s", data["errors"])
        return []

    pr_data = data.get("data", {}).get("repository", {}).get("pullRequest")
    if not pr_data:
        logger.warning("No pull request data found for PR #%d", pr_number)
        return []

    review_threads = pr_data.get("reviewThreads", {}).get("nodes", [])
    return _extract_comments_from_threads(review_threads, only_unresolved)
