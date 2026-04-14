"""
Defines the state structure for the LangGraph agent.

This module contains the `AgentState` TypedDict, which represents the shared
state that is passed between nodes in the agent's workflow graph. It holds
all the necessary information for the agent to function, such as message history,
issue details, and internal counters.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, TypedDict, TYPE_CHECKING

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from app.core.its.issue_tracking_system import Issue, IssueComment
from app.core.types import PlanState, IssueStateType, IssueType, AgentStack

if TYPE_CHECKING:
    from app.agent.runtime import RuntimeSetting


@dataclass
class AgentSummary:
    """Represents a summary entry from an agent role."""

    role: str
    summary: str

    def __post_init__(self):
        """Validate and normalize the fields."""
        if not isinstance(self.role, str):
            raise TypeError("role must be a string")
        if not isinstance(self.summary, str):
            raise TypeError("summary must be a string")

        self.role = self.role.strip()
        self.summary = self.summary.strip()

    def to_markdown(self) -> str:
        """Format the summary as a markdown entry with role prefix."""
        role_prefix = self.role.capitalize()
        return f"**[{role_prefix}]** {self.summary}"


class AgentState(TypedDict):
    """
    Represents the state of the agent graph.

    This state is passed between all nodes in the graph. Each field holds a piece
    of information that nodes can read from or write to, allowing them to
    collaborate and track progress.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    message_history: Annotated[list[BaseMessage], add_messages]
    next_step: str

    # information from the external issue tracking system
    issue_comments: list[IssueComment]
    issue_id: str | None
    issue_name: str | None
    issue_description: str | None
    issue_state: IssueStateType | None
    issue_type: IssueType | None
    issue_skill_level: str | None
    issue_skill_level_reasoning: str | None
    issue_from_todo: bool | None
    issue_is_active: bool | None

    # agent information from settings
    agent_stack: AgentStack
    tech_stack: dict | None
    agent_skill_level: str | None
    agent_summary: list[AgentSummary] | None
    retry_count: int  # Attempts: how often switched between coder and tester
    test_result: str | None
    error_log: str | None  # Optional: Stores the last error explicitly

    # information from the git system
    repo_branch_name: str | None
    pr_review_message: str | None

    plan_content: str | None
    plan_state: PlanState | None

    # the last agent node that is executed
    current_node: str | None
    # the tool calls that was created from the last agent node
    current_tool_calls: list[dict]
    # the human message that was sent from the last agent node
    prompt: str | None
    # the system prompt that was sent from the last agent node
    system_prompt: str | None
    # the working state of the agent
    working_state: str | None
    # message from the system to the user
    user_message: str | None
    last_update: datetime | None
    #
    pr_description: str | None

    @staticmethod
    def init_state(runtime: "RuntimeSetting") -> "AgentState":
        """Initialize the default agent state based on runtime settings."""
        # pylint: disable=import-outside-toplevel
        from app.core.constants import TECH_STACKS

        return {
            # values that are stored in the database
            "issue_id": None,
            "issue_name": None,
            "issue_description": None,
            "issue_comments": [],
            "issue_type": None,
            "issue_skill_level": None,
            "issue_skill_level_reasoning": None,
            "issue_is_active": None,
            "issue_from_todo": None,
            "repo_branch_name": None,
            "plan_content": None,
            "plan_state": None,
            "working_state": None,
            "user_message": None,
            # values that are not stored in the database
            "messages": [],
            "next_step": "",
            "agent_stack": runtime.agent_stack,
            "agent_skill_level": runtime.agent_settings.agent_skill_level,
            "current_node": None,
            "current_tool_calls": [],
            "prompt": None,
            "system_prompt": None,
            "tech_stack": TECH_STACKS[runtime.agent_stack],
        }
