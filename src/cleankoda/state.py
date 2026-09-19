from dataclasses import dataclass

from cleankoda.its import IssueState

@dataclass
class ActiveIssueContext:
  id: str
  title: str
  description: str
  state: IssueState
  state_id: str | None = None
  state_name: str | None = None
  url: str | None = None

  def to_system_prompt_snippet(self) -> str:
    """Formats the issue as a fixed context section for the LLM."""
    desc = self.description.strip() or "No description available."
    return (
        "\n\n=== ACTIVE TICKET / USER STORY ===\n"
        f"ID: {self.id}\n"
        f"Title: {self.title}\n"
        f"State: {self.state}\n"
        f"Description & Criteria:\n{desc}\n"
        "====================================\n"
        "Take into account the specifications, criteria, and constraints of this ticket "
        "during all planning, code generation, and responses.\n"
    )

active_issue: ActiveIssueContext | None = None

def set_active_issue(issue: ActiveIssueContext | None) -> None:
  global active_issue
  active_issue = issue

def get_active_issue() -> ActiveIssueContext | None:
  return active_issue

def clear_active_issue() -> None:
  global active_issue
  active_issue = None
