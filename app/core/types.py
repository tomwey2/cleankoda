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
