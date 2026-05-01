"""
Trello implementation of the IssueProvider interface.

This adapter wraps the existing Trello client functions and adapts them
to the IssueProvider interface, allowing Trello to be used interchangeably
with other issue tracking systems.
"""

import logging
import httpx

from datetime import datetime, timezone

from src.core.extern.its.issue_tracking_system import (
    IssueTrackingSystem,
    Issue,
    IssueComment,
)
from src.core.database.models import AgentSettingsDb
from src.core.types import IssueTrackingSystemType, IssueStateType
from src.core.services.credentials_service import get_credential_by_id

logger = logging.getLogger(__name__)


class TrelloIts(IssueTrackingSystem):
    """
    Trello implementation of the IssueTrackingSystem interface.

    This class wraps the existing Trello client functions and provides
    a consistent interface for issue operations.
    """

    def __init__(self, agent_settings: AgentSettingsDb):
        """
        Initialize the Trello provider.

        Args:
            agent_settings: Agent settings containing Trello credentials and settings
        """
        self.agent_settings = agent_settings

    async def get_issue_by_id(self, issue_id: str) -> Issue | None:
        """Fetch a specific Trello card."""
        credential = get_credential_by_id(self.agent_settings.its_credential_id)
        base_url = self.agent_settings.its_base_url
        base_url = base_url.rstrip("/")
        url = f"{base_url}/cards/{issue_id}"
        headers = {"Accept": "application/json"}
        query = {
            "fields": "name,desc,idList,url",
            "list": "true",
            "key": credential.api_key,
            "token": credential.api_token,
        }

        logger.debug("Trello GET: %s", self.get_safe_url(url, query))
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=query)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch card {issue_id}: {response.text}")

        data = response.json()
        list_info = data.get("list") or {}
        if not data:
            logger.warning("Trello card %s not found", issue_id)
            return None

        state_name = list_info.get("name", "")
        state_type = self.agent_settings.translate_issue_state_to_type(state_name)
        if state_type == IssueStateType.UNKNOWN:
            logger.warning("Could not determine state for card %s", issue_id)

        return Issue(
            id=data.get("id"),
            name=data.get("name", ""),
            description=data.get("desc", ""),
            state_type=state_type,
            state_id=data.get("idList", ""),
            state_name=state_name,
            url=data.get("url", ""),
        )

    async def get_next_issue_from_state(self, state_type: IssueStateType) -> Issue | None:
        """Fetch the next issue from a specific state (Trello list)."""
        state_id, state_name = await self._resolve_trello_state_from_state_type(state_type)
        credential = get_credential_by_id(self.agent_settings.its_credential_id)
        base_url = self.agent_settings.its_base_url
        base_url = base_url.rstrip("/")
        url = f"{base_url}/lists/{state_id}/cards"
        headers = {"Accept": "application/json"}
        query = {"key": credential.api_key, "token": credential.api_token}

        logger.debug("Trello GET: %s", self.get_safe_url(url, query))
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=query)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch cards: {response.text}")

        cards = response.json()
        if not cards:
            logger.warning("No issues found in state %s", state_name)
            return None

        card = cards[0]
        return Issue(
            id=card["id"],
            name=card.get("name", ""),
            description=card.get("desc", ""),
            state_type=state_type,
            state_id=state_id,
            state_name=state_name,
            url=card.get("url", ""),
        )

    async def _resolve_trello_state_from_state_type(
        self, state_type: IssueStateType
    ) -> tuple[str, str]:
        """Resolve the human-readable Trello list name for a given list ID."""
        state_name = self.agent_settings.translate_type_to_issue_state(state_type)
        try:
            trello_lists = await self.get_all_trello_lists()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("Failed to resolve Trello state name for %s: %s", state_name, exc)
            return "", ""

        for trello_list in trello_lists:
            if trello_list["name"] == state_name:
                return trello_list.get("id", ""), trello_list.get("name", "")

        logger.warning("Trello list %s not found when resolving state name", state_name)
        return "", ""

    async def move_issue_to_state(self, issue_id: str, target_state_type: IssueStateType) -> None:
        """Move a issue to a different state (Trello list)."""
        target_state_id, target_state_name = await self._resolve_trello_state_from_state_type(
            target_state_type
        )

        if not target_state_id:
            raise ValueError(
                f"Trello list {target_state_name} ({target_state_type.name}) not found on configured board"
            )

        credential = get_credential_by_id(self.agent_settings.its_credential_id)
        base_url = self.agent_settings.its_base_url
        base_url = base_url.rstrip("/")
        url = f"{base_url}/cards/{issue_id}"
        headers = {"Accept": "application/json"}
        query = {
            "idList": target_state_id,
            "key": credential.api_key,
            "token": credential.api_token,
        }

        logger.debug("Trello PUT: %s", self.get_safe_url(url, query))
        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=headers, params=query)

        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to move card {issue_id} to list {target_state_name}: {response.text}"
            )

    async def add_comment_to_issue(self, issue_id: str, comment: str) -> None:
        """Add a comment to a Trello issue."""
        credential = get_credential_by_id(self.agent_settings.its_credential_id)
        base_url = self.agent_settings.its_base_url
        base_url = base_url.rstrip("/")
        url = f"{base_url}/cards/{issue_id}/actions/comments"
        headers = {"Accept": "application/json"}
        query = {
            "text": comment,
            "key": credential.api_key,
            "token": credential.api_token,
        }

        logger.debug("Trello POST: %s", self.get_safe_url(url, query))
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, params=query)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to add a comment to card {issue_id}: {response.text}")

    async def get_comments_from_issue(self, issue_id: str) -> list[IssueComment]:
        """Fetch all comments for a Trello issue."""
        credential = get_credential_by_id(self.agent_settings.its_credential_id)
        base_url = self.agent_settings.its_base_url
        base_url = base_url.rstrip("/")
        url = f"{base_url}/cards/{issue_id}/actions"
        headers = {"Accept": "application/json"}
        query = {
            "filter": "commentCard",
            "key": credential.api_key,
            "token": credential.api_token,
        }

        logger.debug("Trello GET: %s", self.get_safe_url(url, query))
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=query)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch comments for card {issue_id}: {response.text}")

        data = response.json()
        return [
            IssueComment(
                id=action.get("id"),
                text=action.get("data", {}).get("text", ""),
                author=action.get("memberCreator", {}).get("fullName"),
                date=self._parse_timestamp(action.get("date")),
            )
            for action in data
        ]

    async def create_issue(self, name: str, description: str, state_name: str) -> Issue:
        """Create a new issue in the specified state (Trello list)."""

        trello_lists = await self.get_all_trello_lists()
        target_list = next((data for data in trello_lists if data["name"] == state_name), None)

        if not target_list:
            raise ValueError(f"Trello list '{state_name}' not found on configured board")

        list_id = target_list["id"]
        logger.info("Creating card in list '%s' (id: %s)", state_name, list_id)

        credential = get_credential_by_id(self.agent_settings.its_credential_id)
        base_url = self.agent_settings.its_base_url
        base_url = base_url.rstrip("/")
        url = f"{base_url}/cards"
        headers = {"Accept": "application/json"}
        query = {
            "idList": list_id,
            "name": name,
            "desc": description,
            "key": credential.api_key,
            "token": credential.api_token,
        }

        logger.info("Trello POST: %s", self.get_safe_url(url, query))
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, params=query)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to create card: {response.text}")

        data = response.json()
        return Issue(
            id=data.get("id"),
            name=data.get("name"),
            description=description,
            state_id="",
            state_name=state_name,
            url=data.get("url"),
        )

    async def get_all_trello_lists(self) -> list[dict]:
        """Fetches all lists for the configured Trello issue system."""
        board_id = self.agent_settings.its_container_id
        credential = get_credential_by_id(self.agent_settings.its_credential_id)

        base_url = self.agent_settings.its_base_url
        base_url = base_url.rstrip("/")
        url = f"{base_url}/boards/{board_id}/lists"
        headers = {"Accept": "application/json"}
        query = {"key": credential.api_key, "token": credential.api_token}

        logger.debug("Trello GET: %s", self.get_safe_url(url, query))
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=query)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch lists: {response.text}")

        data = response.json()
        return [{"name": list_item["name"], "id": list_item["id"]} for list_item in data]

    def get_type(self) -> str:
        """Return the provider identifier."""
        return IssueTrackingSystemType.TRELLO

    def _parse_timestamp(self, value: str | None) -> datetime:
        """
        Parse a Trello timestamp string into a datetime object.

        Args:
            value: ISO format timestamp string

        Returns:
            Parsed datetime object with timezone info
        """
        if not value:
            return datetime.now(timezone.utc)

        normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            logger.warning("Failed to parse Trello timestamp '%s'", value)
            return datetime.now(timezone.utc)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed

    def get_safe_url(self, url: str, params: dict) -> str:
        """
        Creates a URL for logging with sensitive parameters masked.
        """
        # Build the full URL including params to parse it
        req = httpx.Request("GET", url, params=params)
        parsed_url = req.url

        # Copy the query parameters, but overwrite the secrets
        new_query_params = []
        for key, value in parsed_url.params.items():
            if key in ["key", "token"]:
                new_query_params.append((key, "SECRET"))
            else:
                new_query_params.append((key, value))

        # Return URL with safe query string
        return str(parsed_url.copy_with(params=new_query_params))
