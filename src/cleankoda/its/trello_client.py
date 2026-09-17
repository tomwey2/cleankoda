import httpx

from cleankoda.its.its import IssueTrackingSystem, Issue, IssueComment
from cleankoda.its.config import IssueState
from cleankoda.config import config

class TrelloClient(IssueTrackingSystem):
    """
    Trello implementation of the IssueTrackingSystem interface.
    """
    def __init__(self) -> None:
        self.api_key: str = config.get_credential_by_key("trello_api_key")
        self.token: str = config.get_credential_by_key("trello_token")
        self.auth_params = {"key": self.api_key, "token": self.token}

    async def get_states(self) -> list[dict]:
        """Fetch all states (Trello lists) from the board."""
        board_id = config.its_container_id

        url = f"https://api.trello.com/1/boards/{board_id}/lists"
        headers = {"Accept": "application/json"}
        query = {"key": self.api_key, "token": self.token}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=query)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch lists: {response.text}")

        data = response.json()
        return [{"name": list_item["name"], "id": list_item["id"]} for list_item in data]


    async def get_issue(self, issue_id: str) -> Issue:
        """Fetch details for a single Trello card including its list metadata."""

        url = f"{config.its_base_url}/cards/{issue_id}"
        params = {**self.auth_params, "fields": "name,desc,idList,url", "list": "true"}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        list_info = data.get("list") or {}
        return Issue(
            id=data.get("id", issue_id),
            name=data.get("name", ""),
            description=data.get("desc", ""),
            state_id=data.get("idList", ""),
            state_name=list_info.get("name", ""),
            url=data.get("url", ""),
        )


    async def get_issues_from_state(self, state: IssueState) -> list[Issue]:
        """Fetch all issues from a specific state (i.e. Trello list)."""
        trello_states: list[dict] = await self.get_states()
        list_name: str = state.value
        match = next((item for item in trello_states if item.get("name") == list_name), None)
        list_id: str = match["id"] if match else None

        url = f"{config.its_base_url}/lists/{list_id}/cards"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=self.auth_params)
        response.raise_for_status()

        cards = response.json()
        return [
            Issue(
                id=card["id"],
                name=card["name"],
                description=card["desc"],
                state_id=list_id,
                state_name=list_name,
                url=card.get("url", ""),
            )
            for card in cards
        ]


    async def move_issue_to_state(self, issue_id: str, state: IssueState) -> None:
        pass

    async def add_comment(self, issue_id: str, comment: str) -> None:
        pass


    async def get_comments(self, issue_id: str) -> list[IssueComment]:
        pass

    async def create_issue(self, name: str, description: str, state: IssueState) -> Issue:
        pass
