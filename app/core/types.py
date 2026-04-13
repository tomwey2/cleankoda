"""
Defines the types and enums of the system.
"""

from enum import StrEnum


class SkillLevelType(StrEnum):
    """Defines the types of skill levels."""

    UNKNOWN = "UNKNOWN"
    JUNIOR = "JUNIOR"
    SENIOR = "SENIOR"

    @classmethod
    def from_string(cls, value: str) -> "SkillLevelType":
        """Convert a string to a SkillLevelType, normalizing whitespace and case."""
        normalized = value.strip().upper() if value else ""
        try:
            return cls(normalized)
        except ValueError:
            return cls.UNKNOWN


class GenderType(StrEnum):
    """Defines the types of genders."""

    UNKNOWN = "UNKNOWN"
    MALE = "MALE"
    FEMALE = "FEMALE"

    @classmethod
    def from_string(cls, value: str) -> "GenderType":
        """Convert a string to a GenderType, normalizing whitespace and case."""
        normalized = value.strip().upper() if value else ""
        try:
            return cls(normalized)
        except ValueError:
            return cls.UNKNOWN


class IssueTrackingSystemType(StrEnum):
    """Defines the types of issue tracking systems."""

    UNKNOWN = "UNKNOWN"
    TRELLO = "TRELLO"
    GITHUB = "GITHUB"
    JIRA = "JIRA"

    @classmethod
    def from_string(cls, value: str) -> "IssueTrackingSystemType":
        """Convert a string to an IssueTrackingSystemType, normalizing whitespace and case."""
        normalized = value.strip().upper() if value else ""
        try:
            return cls(normalized)
        except ValueError:
            return cls.UNKNOWN


class PlanState(StrEnum):
    """Defines the states of the plan."""

    UNKNOWN = "UNKNOWN"
    REQUESTED = "REQUESTED"
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    @classmethod
    def from_string(cls, value: str) -> "PlanState":
        """Convert a string to a PlanState, normalizing whitespace and case."""
        normalized = value.strip().upper() if value else ""
        try:
            return cls(normalized)
        except ValueError:
            return cls.UNKNOWN


class IssueStateType(StrEnum):
    """Defines the states of issues."""

    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    DONE = "DONE"


class IssueType(StrEnum):
    """Defines the types of issues."""

    UNKNOWN = "UNKNOWN"
    CODING = "CODING"
    BUGFIXING = "BUGFIXING"
    ANALYZING = "ANALYZING"

    @classmethod
    def from_string(cls, value: str) -> "IssueType":
        """Convert a string to a IssueType, normalizing whitespace and case."""
        normalized = value.strip().upper() if value else ""
        try:
            return cls(normalized)
        except ValueError:
            return cls.UNKNOWN


class AgentStack(StrEnum):
    """Supported technology stacks for the agent runtime."""

    BACKEND = "BACKEND"
    FRONTEND = "FRONTEND"
    GRADLE_NODE = "GRADLE_NODE"
