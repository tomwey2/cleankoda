from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from cleankoda.its.config import IssueState


class AgentActivity(Enum):
    IDLE = "Idle"
    PLANNING = "Planning"
    REVIEWING_PLAN = "Reviewing Plan"
    CODING = "Coding"
    TESTING = "Testing"
    REVIEWING_CODE = "Reviewing Code"
    ERROR = "Error"


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


@dataclass
class SessionState:
    activity: AgentActivity = AgentActivity.IDLE
    active_issue: ActiveIssueContext | None = None
    current_task_description: str | None = None
    last_error: str | None = None
    status_slots: dict[str, str] = field(default_factory=dict)
    _listeners: list[Callable[["SessionState"], None]] = field(
        default_factory=list, repr=False
    )

    def subscribe(self, callback: Callable[["SessionState"], None]) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def notify(self) -> None:
        for listener in list(self._listeners):
            try:
                listener(self)
            except Exception:
                pass

    def get_combined_status(self) -> str:
        if not self.status_slots:
            return ""
        return " | ".join(self.status_slots.values())


_session_state = SessionState()


def get_session_state() -> SessionState:
    return _session_state


def get_activity() -> AgentActivity:
    return _session_state.activity


def set_activity(
    activity: AgentActivity, task_description: str | None = None
) -> None:
    _session_state.activity = activity
    _session_state.current_task_description = task_description
    if activity != AgentActivity.ERROR:
        _session_state.last_error = None
    _session_state.notify()


def set_error_state(error_message: str) -> None:
    _session_state.activity = AgentActivity.ERROR
    _session_state.last_error = error_message
    _session_state.notify()


def set_active_issue(issue: ActiveIssueContext | None) -> None:
    _session_state.active_issue = issue
    _session_state.notify()


def get_active_issue() -> ActiveIssueContext | None:
    return _session_state.active_issue


def clear_active_issue() -> None:
    _session_state.active_issue = None
    _session_state.notify()


def set_status(source: str, message: str) -> None:
    _session_state.status_slots[source] = message
    _session_state.notify()


def clear_status(source: str) -> None:
    if source in _session_state.status_slots:
        del _session_state.status_slots[source]
        _session_state.notify()
