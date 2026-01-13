"""
Defines the Tester agent node for the agent graph.

The Tester is a specialist agent responsible for verifying code changes,
running tests, and reporting the results.
"""

import logging
import os
import re
import subprocess
from typing import Any, Dict, Literal, Optional
import requests

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field

from agent.state import AgentState
from agent.tools.local_tools import report_test_result
from agent.utils import (
    filter_messages_for_llm,
    get_workspace,
    load_system_prompt,
    log_agent_response,
)

logger = logging.getLogger(__name__)


class TesterResult(BaseModel):
    """Call this tool ONLY when you have completed the testing process."""

    result: Literal["pass", "fail"] = Field(
        ...,
        description="The final result. 'pass' if tests and PR are successful, 'fail' otherwise.",
    )
    summary: str = Field(
        ...,
        description="A short summary of what happened (e.g. 'PR created at xyz' "
        + "or 'Tests failed because of NPE').",
    )


def create_tester_node(llm, tools, agent_stack):
    """
    Factory function that creates the Tester agent node.

    Args:
        llm: The language model to be used by the tester.
        tools: A list of tools available to the tester.
        agent_stack: The technology stack to load the correct system prompt.

    Returns:
        A function that represents the tester node.
    """
    sys_msg = load_system_prompt(agent_stack, "tester")
    llm_with_tools = llm.bind_tools(tools + [report_test_result])

    async def tester_node(state: AgentState):
        # Filter messages to keep only recent relevant context (original task + last 15 messages)
        filtered_messages = filter_messages_for_llm(state["messages"], max_messages=15)
        current_messages = [SystemMessage(content=sys_msg)] + filtered_messages

        # LLM Aufruf
        response = await llm_with_tools.ainvoke(current_messages)

        has_content = bool(response.content)
        has_tool_calls = bool(getattr(response, "tool_calls", []))

        if has_content or has_tool_calls:
            log_agent_response("tester", response)

        report_args = _get_report_result_args(response)
        if tests_passed(report_args):
            summary = report_args.get("summary", "")
            detail = f": {summary}" if summary else ""
            logger.info("Tester node reported PASS result%s", detail)

            has_changes, _ = _execute_git_status()
            if has_changes:
                logger.info("Changes detected, executing Git workflow...")

                if not _execute_git_add():
                    logger.error("Git add failed, skipping remaining Git operations")
                elif not _execute_git_commit("fix: automated test-driven changes"):
                    logger.error("Git commit failed, skipping remaining Git operations")
                else:
                    push_success, push_msg = _execute_git_push()
                    if push_success:
                        pr_success, pr_msg = _execute_create_pull_request(
                            title="Automated Fix",
                            body=f"Automated changes after successful tests.\n\n{summary}",
                        )
                        if pr_success:
                            logger.info("Git workflow completed successfully: %s", pr_msg)
                        else:
                            logger.error("PR creation failed: %s", pr_msg)
                    else:
                        logger.error("Git push failed: %s", push_msg)
            else:
                logger.info("No changes detected, skipping Git workflow")

        return {"messages": [response]}

    return tester_node


def _get_report_result_args(response: Any) -> Optional[Dict[str, Any]]:
    """
    Returns the argument payload of the report_test_result tool call if present.
    """
    for tool_call in getattr(response, "tool_calls", []) or []:
        if tool_call.get("name") == "report_test_result":
            return tool_call.get("args", {})
    return None


def tests_passed(tool_args: Optional[Dict[str, Any]]) -> bool:
    """
    Determines whether the provided tool arguments represent a passing test run.
    """
    if not tool_args:
        return False
    result = tool_args.get("result")
    return isinstance(result, str) and result.lower() == "pass"


def _execute_git_status() -> tuple[bool, str]:
    """
    Executes git status and checks if there are changes.
    Returns (has_changes, output).
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=get_workspace(),
            check=True,
            capture_output=True,
            text=True,
        )
        has_changes = bool(result.stdout.strip())
        logger.info("Git status check: %s changes found", "Some" if has_changes else "No")
        return has_changes, result.stdout
    except subprocess.CalledProcessError as e:
        logger.error("Git status failed: %s", e.stderr)
        return False, f"Error: {e.stderr}"


def _execute_git_add() -> bool:
    """
    Adds all changes to staging area.
    Returns True if successful.
    """
    try:
        subprocess.run(
            ["git", "add", "."],
            cwd=get_workspace(),
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Git add successful")
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Git add failed: %s", e.stderr)
        return False


def _execute_git_commit(message: str) -> bool:
    """
    Commits staged changes with the given message.
    Returns True if successful.
    """
    try:
        subprocess.run(
            ["git", "config", "user.email", "agent@bot.com"],
            cwd=get_workspace(),
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Coding Agent"],
            cwd=get_workspace(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=get_workspace(),
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Git commit successful: %s", message)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Git commit failed: %s", e.stderr)
        return False


def _execute_git_push() -> tuple[bool, str]:
    """
    Pushes the current branch to origin.
    Returns (success, message).
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.error("GITHUB_TOKEN missing for git push")
        return False, "ERROR: GITHUB_TOKEN missing"

    try:
        current_branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=get_workspace(),
            text=True,
        ).strip()

        if current_branch in ["main", "master"]:
            logger.warning("Attempted to push to default branch '%s'", current_branch)
            return False, f"ERROR: Cannot push to default branch '{current_branch}'"

        current_url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=get_workspace(),
            text=True,
        ).strip()

        if "https://" in current_url and "@" not in current_url:
            auth_url = current_url.replace("https://", f"https://{token}@")
            subprocess.run(
                ["git", "remote", "set-url", "origin", auth_url],
                cwd=get_workspace(),
                check=True,
            )

        result = subprocess.run(
            ["git", "push", "-u", "origin", "HEAD"],
            cwd=get_workspace(),
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info("Git push successful")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        safe_stderr = e.stderr.replace(token, "***") if token else e.stderr
        logger.error("Git push failed: %s", safe_stderr)
        return False, f"Push FAILED: {safe_stderr}"


def _execute_create_pull_request(title: str, body: str) -> tuple[bool, str]:
    """
    Creates or updates a GitHub Pull Request.
    Returns (success, message).
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.error("GITHUB_TOKEN missing for PR creation")
        return False, "ERROR: GITHUB_TOKEN missing"

    try:
        remote_url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=get_workspace(),
            text=True,
        ).strip()

        match = re.search(r"github\.com[:/](.+)/(.+?)(\.git)?$", remote_url)
        if not match:
            return False, f"ERROR: Could not parse Owner/Repo from URL: {remote_url}"

        owner, repo = match.group(1), match.group(2)

        current_branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=get_workspace(),
            text=True,
        ).strip()

        if current_branch in ["main", "master"]:
            return False, "ERROR: You are on main/master. Create a feature branch first!"

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        params = {"head": f"{owner}:{current_branch}", "state": "open"}
        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            pulls = response.json()
            if pulls:
                existing_pr = pulls[0]
                pr_number = existing_pr.get("number")
                pr_url = existing_pr.get("html_url")
                comment_url = f"https://api.github.com/repos/\
                    {owner}/{repo}/issues/{pr_number}/comments"
                comment_payload = {"body": f"**Automated Update:**\n\n{body}"}
                comment_response = requests.post(
                    comment_url, json=comment_payload, headers=headers, timeout=10
                )
                if comment_response.status_code == 201:
                    logger.info("Added comment to existing PR: %s", pr_url)
                    return True, f"SUCCESS: Added comment to existing PR: {pr_url}"
                return False, f"ERROR adding comment: {comment_response.status_code}"

        payload = {"title": title, "body": body, "head": current_branch, "base": "main"}
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code == 422:
            logger.info("Target 'main' not found, trying 'master'...")
            payload["base"] = "master"
            response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code == 201:
            pr_url = response.json().get("html_url")
            logger.info("Pull Request created: %s", pr_url)
            return True, f"SUCCESS: Pull Request created: {pr_url}"

        return False, f"ERROR creating PR: {response.status_code} - {response.text}"
    except Exception as e: # pylint: disable=broad-exception-caught
        logger.error("PR creation failed: %s", str(e))
        return False, f"ERROR: {str(e)}"
