import os
import sys
from mcp.server.fastmcp import FastMCP

from cleankoda.its.its import IssueTrackingSystem, IssueState
from cleankoda.its.trello_client import TrelloClient


# Initialize MCP instance and tracker
mcp = FastMCP("Issue-Tracker-Bridge")
its: IssueTrackingSystem = TrelloClient()


# Deploy generic tools
@mcp.tool()
async def get_issues(state: IssueState = IssueState.TODO) -> str:
  """Retrieves a list of tasks/issues based on status."""
  issues = await its.get_issues_from_state(state=state)
  if not issues:
    return f"No issues with status '{state}' found."

  return "\n".join(
      [f"- [{i.id}] {i.title}: {i.description[:80]}..." for i in issues]
  )


@mcp.tool()
async def get_issue_details(issue_id: str) -> dict:
  """Retrieves the full details (title, description, URL) of a ticket."""
  issue = await its.get_issue(issue_id)
  return {
      "id": issue.id,
      "title": issue.title,
      "description": issue.description,
      "state_id": issue.state_id,
      "state_name": issue.state_name,
      "url": issue.url,
  }

# Start server
if __name__ == "__main__":
  mcp.run(transport="stdio")
