from enum import Enum
from cleankoda.config import config

class IssueState(str, Enum):
    BACKLOG = config.its_state_backlog
    TODO = config.its_state_todo
    IN_PROGRESS = config.its_state_in_progress
    IN_REVIEW = config.its_state_in_review
    DONE = config.its_state_done

map_state_name_to_issue_state: dict[str, IssueState] = {
    config.its_state_backlog: IssueState.BACKLOG,
    config.its_state_todo: IssueState.TODO,
    config.its_state_in_progress: IssueState.IN_PROGRESS,
    config.its_state_in_review: IssueState.IN_REVIEW,
    config.its_state_done: IssueState.DONE,
}

def from_state_name(state_name: str) -> IssueState:
    state = map_state_name_to_issue_state.get(state_name)
    if not state:
        raise ValueError(f"state_name {state_name} is not defined.")
