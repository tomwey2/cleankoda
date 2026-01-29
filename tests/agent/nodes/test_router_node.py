"""Tests for the router node task-role propagation."""

import pytest

from app.agent.nodes import router as router_module
from app.agent.state import PlanState


class DummyLLM:
    """Simple stub to control router responses in tests."""

    def __init__(self, response):
        self._response = response

    def with_structured_output(self, *_args, **_kwargs):
        return self

    async def ainvoke(self, *_args, **_kwargs):
        return self._response


@pytest.mark.asyncio
async def test_router_sets_task_role_for_coder():
    llm = DummyLLM(
        router_module.RouterDecision(
            type="coding", skill_level="junior", reasoning="simple feature"
        )
    )
    router_node = router_module.create_router_node(llm)
    state = {
        "messages": [],
        "agent_skill_level": "senior",
        "plan_state": PlanState.APPROVED,
    }

    result = await router_node(state)

    assert result["next_step"] == "coder"
    assert result["task_role"] == "coder"


@pytest.mark.asyncio
async def test_router_sets_task_role_none_on_reject():
    llm = DummyLLM(
        router_module.RouterDecision(
            type="coding", skill_level="senior", reasoning="needs senior"
        )
    )
    router_node = router_module.create_router_node(llm)
    state = {
        "messages": [],
        "agent_skill_level": "junior",
        "plan_state": PlanState.REQUESTED,
    }

    result = await router_node(state)

    assert result["next_step"] == "reject"
    assert result["task_role"] is None
