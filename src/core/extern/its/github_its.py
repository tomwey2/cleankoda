"""
GitHub Projects v2 implementation of the IssueProvider interface.

This module provides a GitHubProvider class that wraps the GitHub Projects v2
GraphQL API client and implements the IssueProvider interface for consistent
issue operations across different systems.
"""

import logging
from typing import Any
from datetime import datetime, timezone
import httpx

from src.core.extern.its.issue_tracking_system import (
    IssueComment,
    IssueTrackingSystem,
    Issue,
)
from src.core.database.models import AgentSettingsDb
from src.core.types import IssueStateType
from src.core.services.credentials_service import get_credential_by_id

logger = logging.getLogger(__name__)

GITHUB_GRAPHQL_ENDPOINT = "/graphql"


class GitHubIts(IssueTrackingSystem):
    """
    GitHub Projects v2 implementation of the IssueTrackingSystem interface.

    This class wraps the GitHub GraphQL API client functions and provides
    a consistent interface for issue operations.
    """

    def __init__(self, agent_settings: AgentSettingsDb):
        """
        Initialize the GitHub provider.

        Args:
            agent_settings: Agent settings containing GitHub project configuration.
        """
        self.agent_settings = agent_settings
        self.credential = get_credential_by_id(agent_settings.its_credential_id)
        if not self.credential or not self.credential.api_token:
            raise ValueError("GitHub token not configured.")
        if not self.agent_settings.its_base_url:
            raise ValueError("GitHub API base URL not configured for ITS.")
        self.base_url = self.agent_settings.its_base_url.rstrip("/")

    async def _execute_graphql(
        self,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a GraphQL query against the GitHub API."""
        url = f"{self.base_url}{GITHUB_GRAPHQL_ENDPOINT}"

        headers = {
            "Authorization": f"Bearer {self.credential.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = {"query": query, "variables": variables}

        logger.info("GitHub GraphQL POST: %s", url)
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)

        if response.status_code != 200:
            raise RuntimeError(f"GitHub GraphQL request failed: {response.text}")

        data = response.json()
        if "errors" in data:
            error_messages = [e.get("message", str(e)) for e in data["errors"]]
            raise RuntimeError(f"GitHub GraphQL errors: {'; '.join(error_messages)}")

        return data

    async def get_states(self) -> list[dict]:
        """Fetch all states (columns) from the GitHub Project."""
        project_id = self.agent_settings.its_container_identifier

        query = """
        query($projectId: ID!) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    field(name: "Status") {
                        ... on ProjectV2SingleSelectField {
                            id
                            options {
                                id
                                name
                            }
                        }
                    }
                }
            }
        }
        """

        variables = {"projectId": project_id}
        data = await self._execute_graphql(query, variables)

        field = data.get("data", {}).get("node", {}).get("field", {})
        options = field.get("options", [])

        return [{"id": opt["id"], "name": opt["name"]} for opt in options]

    async def get_status_field_id(self) -> str:
        """Get the ID of the Status field for the project."""
        project_id = self.agent_settings.its_container_identifier

        query = """
        query($projectId: ID!) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    field(name: "Status") {
                        ... on ProjectV2SingleSelectField {
                            id
                        }
                    }
                }
            }
        }
        """

        variables = {"projectId": project_id}
        data = await self._execute_graphql(query, variables)

        field = data.get("data", {}).get("node", {}).get("field", {})
        field_id = field.get("id")

        if not field_id:
            raise RuntimeError("Status field not found in project")

        return field_id

    async def get_issue_by_id(self, issue_id: str) -> Issue | None:
        """Fetch a specific issue (project item) by ID."""
        query = """
        query($itemId: ID!) {
            node(id: $itemId) {
                ... on ProjectV2Item {
                    id
                    fieldValueByName(name: "Status") {
                        ... on ProjectV2ItemFieldSingleSelectValue {
                            optionId
                            name
                        }
                    }
                    content {
                        __typename
                        ... on Issue {
                            id
                            title
                            body
                            url
                        }
                        ... on DraftIssue {
                            id
                            title
                            body
                        }
                    }
                }
            }
        }
        """

        variables = {"itemId": issue_id}
        data = await self._execute_graphql(query, variables)

        node = data.get("data", {}).get("node")
        if not node:
            return None

        status_field = node.get("fieldValueByName") or {}
        content = node.get("content") or {}

        if not content:
            logger.warning("GitHub Issue %s not found", issue_id)
            return None

        state_type = self.agent_settings.translate_issue_state_to_type(status_field.get("name", ""))
        if state_type == IssueStateType.UNKNOWN:
            logger.warning("Could not determine state for card %s", issue_id)

        return Issue(
            id=node.get("id", issue_id),
            name=content.get("title", ""),
            description=content.get("body", ""),
            state_type=state_type,
            state_id=status_field.get("optionId", ""),
            state_name=status_field.get("name", ""),
            url=content.get("url", ""),
        )

    async def get_issues_from_state(self, state_type: IssueStateType) -> list[Issue]:
        """
        Fetch all issues from a specific state (column).

        Note: For GitHub Projects, we need to resolve the column name from ID
        first, then fetch items. The state_id here is the column option ID.
        """
        state_id = self.agent_settings.translate_type_to_issue_state(state_type)
        project_id = self.agent_settings.its_container_identifier

        query = """
        query($projectId: ID!) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    field(name: "Status") {
                        ... on ProjectV2SingleSelectField {
                            id
                            options {
                                id
                                name
                            }
                        }
                    }
                }
            }
        }
        """

        variables = {"projectId": project_id}
        data = await self._execute_graphql(query, variables)

        field = data.get("data", {}).get("node", {}).get("field", {})
        options = field.get("options", [])

        target_column = next((opt for opt in options if opt["id"] == state_id), None)

        if not target_column:
            logger.warning("Column with ID %s not found", state_id)
            return []

        items = await self.get_items_from_column(target_column["name"])

        return [
            Issue(
                id=item["id"],
                name=item["title"],
                description=item["body"] or "",
                state_type=state_type,
                state_id=state_id,
                state_name=target_column["name"],
                url=item.get("url", ""),
            )
            for item in items
        ]

    async def move_issue_to_state(self, issue_id: str, target_state_type: IssueStateType) -> None:
        """Move a issue to a different state (column)."""
        state_id = self.agent_settings.translate_type_to_issue_state(target_state_type)
        project_id = self.agent_settings.its_container_identifier
        field_id = await self.get_status_field_id()

        mutation = """
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
            updateProjectV2ItemFieldValue(
                input: {
                    projectId: $projectId
                    itemId: $itemId
                    fieldId: $fieldId
                    value: { singleSelectOptionId: $optionId }
                }
            ) {
                projectV2Item {
                    id
                }
            }
        }
        """

        variables = {
            "projectId": project_id,
            "itemId": issue_id,
            "fieldId": field_id,
            "optionId": state_id,
        }

        await self._execute_graphql(mutation, variables)
        logger.info("Moved item %s to column %s", issue_id, state_id)

    async def add_comment_to_issue(self, issue_id: str, comment: str) -> None:
        """
        Add a comment to a GitHub issue.

        Note: For GitHub Projects, we need the issue ID (content_id), not the
        project item ID. If the issue_id is a project item ID, we need to
        extract the content ID first.
        """
        # First, resolve the ID to get the actual Issue ID if it's a ProjectV2Item
        resolved_issue_id = await self._resolve_to_issue_id(issue_id)

        mutation = """
        mutation($issueId: ID!, $body: String!) {
            addComment(input: { subjectId: $issueId, body: $body }) {
                commentEdge {
                    node {
                        id
                    }
                }
            }
        }
        """

        variables = {"issueId": resolved_issue_id, "body": comment}
        await self._execute_graphql(mutation, variables)
        logger.info("Added comment to issue %s", resolved_issue_id)

    async def get_comments_from_issue(self, issue_id: str) -> list[IssueComment]:
        """Fetch all comments for a GitHub issue."""
        query = """
        query($issueId: ID!) {
            node(id: $issueId) {
                ... on Issue {
                    comments(first: 100) {
                        nodes {
                            id
                            body
                            author {
                                login
                            }
                            createdAt
                        }
                    }
                }
                ... on ProjectV2Item {
                    content {
                        ... on Issue {
                            comments(first: 100) {
                                nodes {
                                    id
                                    body
                                    author {
                                        login
                                    }
                                    createdAt
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        variables = {"issueId": issue_id}
        data = await self._execute_graphql(query, variables)

        node = data.get("data", {}).get("node", {})

        # Try to get comments directly (if it's an Issue)
        comments = node.get("comments", {}).get("nodes", [])

        # If no comments found, try to get from ProjectV2Item content
        if not comments:
            content = node.get("content", {})
            comments = content.get("comments", {}).get("nodes", [])

        return [
            IssueComment(
                id=comment["id"],
                text=comment["body"],
                author=comment.get("author", {}).get("login", "unknown"),
                date=self._parse_timestamp(comment["createdAt"]),
            )
            for comment in comments
        ]

    async def create_issue(self, name: str, description: str, state_name: str) -> Issue:
        """Create a new issue (draft issue) in the specified state (column)."""

        project_id = self.its_container_identifier

        mutation = """
        mutation($projectId: ID!, $title: String!, $body: String!) {
            addProjectV2DraftIssue(
                input: {
                    projectId: $projectId
                    title: $title
                    body: $body
                }
            ) {
                projectItem {
                    id
                }
            }
        }
        """

        variables = {
            "projectId": project_id,
            "title": name,
            "body": description,
        }

        data = await self._execute_graphql(mutation, variables)
        item_id = data["data"]["addProjectV2DraftIssue"]["projectItem"]["id"]

        await self.move_item_to_named_column(item_id, state_name)

        return Issue(
            id=item_id,
            name=name,
            description=description,
            state_id="",
            state_name=state_name,
            url="",
        )

    def get_type(self) -> str:
        """Return the provider identifier."""
        return "github"

    def _parse_timestamp(self, value: str | None) -> datetime:
        """
        Parse a GitHub timestamp string into a datetime object.

        Args:
            value: ISO format timestamp string.

        Returns:
            Parsed datetime object with timezone info.
        """
        if not value:
            return datetime.now(timezone.utc)

        normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            logger.warning("Failed to parse GitHub timestamp '%s'", value)
            return datetime.now(timezone.utc)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed

    async def move_item_to_column(
        self,
        item_id: str,
        column_id: str,
    ) -> None:
        """
        Move a project item to a different column (status).

        Args:
            item_id: The project item node ID.
            column_id: The target column/status option ID.
        """
        project_id = self.its_container_identifier
        field_id = await self.get_status_field_id()

        mutation = """
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
            updateProjectV2ItemFieldValue(
                input: {
                    projectId: $projectId
                    itemId: $itemId
                    fieldId: $fieldId
                    value: { singleSelectOptionId: $optionId }
                }
            ) {
                projectV2Item {
                    id
                }
            }
        }
        """

        variables = {
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": field_id,
            "optionId": column_id,
        }

        await self._execute_graphql(mutation, variables)
        logger.info("Moved item %s to column %s", item_id, column_id)

    async def move_item_to_named_column(
        self,
        item_id: str,
        column_name: str,
        agent_settings: AgentSettingsDb,
    ) -> str:
        """
        Move a project item to a column identified by name.

        Returns:
            The ID of the target column.
        """
        columns = await self.get_project_columns()
        target_column = next((col for col in columns if col["name"] == column_name), None)

        if not target_column:
            raise ValueError(f"Column '{column_name}' not found in project")

        await self.move_item_to_column(item_id, target_column["id"])
        return target_column["id"]
