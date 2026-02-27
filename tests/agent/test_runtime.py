"""Unit tests for runtime stack resolution."""

from app.agent.runtime import _resolve_agent_stack
from app.agent.state import AgentStack


def test_resolve_agent_stack_returns_conductor_when_env_set():
    """Explicit AGENT_STACK='conductor' should resolve to AgentStack.CONDUCTOR."""

    result = _resolve_agent_stack("conductor")

    assert result == AgentStack.CONDUCTOR


def test_resolve_agent_stack_derives_from_workbench(monkeypatch):
    """When AGENT_STACK is unset, derive stack based on workbench name."""

    monkeypatch.setattr("app.agent.runtime.get_workbench", lambda: "workbench-frontend")

    result = _resolve_agent_stack(None)

    assert result == AgentStack.FRONTEND


def test_resolve_agent_stack_defaults_to_backend_for_unknown_workbench(monkeypatch):
    """Fallback should be backend when workbench name is not recognized."""

    monkeypatch.setattr("app.agent.runtime.get_workbench", lambda: "workbench-backend")

    result = _resolve_agent_stack("")

    assert result == AgentStack.BACKEND


def test_resolve_agent_stack_derives_conductor_from_java_node_workbench(monkeypatch):
    """workbench-java-node should derive to AgentStack.CONDUCTOR."""

    monkeypatch.setattr("app.agent.runtime.get_workbench", lambda: "workbench-java-node")

    result = _resolve_agent_stack(None)

    assert result == AgentStack.CONDUCTOR
