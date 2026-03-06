# Message Handling Architecture

## Overview

The agent uses a dual-message system to maintain both per-node conversation context and complete history preservation. This architecture ensures clean context for each LLM node while preserving the complete interaction history.

## Message Fields in AgentState

### 1. `messages` (Per-Node Stack)

- **Type**: `Annotated[list[BaseMessage], add_messages]`
- **Purpose**: Current node's message stack for LLM context
- **Scope**: Single node execution, reset on node switch
- **Usage**: LLM context for current node operations
- **Managed by**: Standard LangGraph `ToolNode` and agent nodes

### 2. `message_history` (Complete History)

- **Type**: `Annotated[list[BaseMessage], add_messages]`
- **Purpose**: Complete conversation history across all nodes
- **Scope**: Entire agent execution lifecycle
- **Usage**: Audit trail, debugging, full context preservation

## Message Flow

### Node Switch (e.g., coder → tester)

When switching between nodes:

1. **Detection**: `state.get("current_node") != node_name` in `invoke_tool_node`
2. **Preservation**: Old `messages` are copied to `message_history`
3. **Clearing**: Old messages are removed using `RemoveMessage` instances
4. **Reset**: New `messages` stack contains only the new AIMessage response
5. **Previous Node Summary**: The `human_prompt` is rendered from templates (e.g., `prompt_testing.md`) and includes `agent_summary` entries from the previous node

**Message Clearing Mechanism**:

LangGraph's `add_messages` reducer doesn't support replacement - it only appends. To clear messages at node switch, we use `RemoveMessage`:

```python
# Create RemoveMessage for each old message
remove_messages = [
    RemoveMessage(id=msg.id) for msg in old_messages if msg.id
]
# Return removal markers + new response
messages_to_add = remove_messages + [response]
```

This ensures the `messages` field is truly reset at node boundaries.

### Tool Call Loop (same node)

When a node makes multiple tool calls:

1. **Detection**: `state.get("current_node") == node_name`
2. **Preservation**: Existing `messages` are retained
3. **Filtering**: `filter_messages_for_llm` applied to keep recent context
4. **Accumulation**: Standard `ToolNode` automatically adds ToolMessages to `messages`:

   ```python
   [
       SystemMessage(content=system_prompt),
       HumanMessage(content=human_prompt),
       ...filtered_existing_messages,
       AIMessage(with tool_calls),
       ToolMessage(tool results)  # Added by ToolNode
   ]
   ```

## Message Sequence for LLM Calls

### Valid Sequence (Mistral-compatible)

```
SystemMessage → HumanMessage → [ToolMessage]* → (next LLM call)
```

The sequence must end with either:
- `HumanMessage` (for initial calls)
- `ToolMessage` (for tool call loops)

### Invalid Sequence (causes API errors)

```
SystemMessage → HumanMessage → AIMessage → ToolMessage → AIMessage
```

❌ Ending with `AIMessage` violates Mistral's message order requirements.

## Implementation Details

### `invoke_tool_node` (`app/agent/nodes/base.py`)

Core function managing the per-node message stack:

```python
# Node switch detection
is_node_switch = state.get("current_node") != node_name

if is_node_switch:
    # Fresh start: system + human prompts only
    current_messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ]
else:
    # Tool call loop: use filtered existing messages directly
    existing_messages = state.get("messages", [])
    current_messages = filter_messages_for_llm(
        existing_messages, max_messages=max_messages
    )
```

**Returns on node switch**:

```python
# Clear old messages using RemoveMessage
messages_to_add = [response]
if is_node_switch:
    old_messages = state.get("messages", [])
    if old_messages:
        # Create RemoveMessage for each old message
        remove_messages = [
            RemoveMessage(id=msg.id) for msg in old_messages if msg.id
        ]
        messages_to_add = remove_messages + [response]

{
    "messages": messages_to_add,         # RemoveMessages + new response
    "message_history": old_messages,     # Preservation
    "current_node": node_name,
    ...
}
```

**Returns on tool call loop**:

```python
{
    "messages": [response],              # Just the new AIMessage
    "current_node": node_name,
    ...
}
```

### Standard ToolNode (`app/agent/graph.py`)

The architecture uses LangGraph's standard `ToolNode` without any custom wrapper:

```python
# Tool Nodes
workflow.add_node("tools_coder", ToolNode(coder_tools))
workflow.add_node("tools_analyst", ToolNode(analyst_tools))
workflow.add_node("tools_tester", ToolNode(tester_tools))
```

**Why this works**: `ToolNode` automatically updates the `messages` field with ToolMessages. Since `messages` is now the per-node stack (not global history), this naturally provides the correct context for the next LLM call.

## Prompt Templates and Summaries

### Template Structure

Each node has a prompt template (e.g., `prompts/prompt_testing.md`):

```markdown
# TASK

Test the code.

{% if agent_summary %}

## PREVIOUS NODE SUMMARY

The previous agent completed the following work:

{% for summary in agent_summary %}
- **[{{ summary.role }}]** {{ summary.summary }}
{% endfor %}

{% endif %}
```

### Summary Extraction

Summaries come from `agent_summary` field, populated by:

1. **finish_task tool**: Coder/Analyst nodes
   ```python
   finish_task(summary="Created REST API endpoints")
   ```

2. **report_test_result tool**: Tester node
   ```python
   report_test_result(result="pass", summary="All tests passed")
   ```

The `record_finish_task_summary` and tester's `_llm_response_hook` extract these summaries and store them in `state["agent_summary"]`.

## Node-Specific Behavior

### Router Node

- **Does NOT use** per-node message management
- Uses structured output with minimal context (`max_messages=3`)
- Reads from `messages` for routing decisions (not reset between calls)

### Analyst, Coder, Tester Nodes

- **Use** `messages` for per-node LLM context
- **Receive** previous node summaries via prompt templates
- **Maintain** isolated conversation stacks during tool call loops
- **Preserve** old messages to `message_history` on node switch

## Benefits

### 1. Context Isolation

Each node starts with a clean slate, receiving only:
- Its specific system prompt
- Task description
- Summary of previous node's work

This prevents context pollution and confusion.

### 2. Tool Call Continuity

Within a node, the conversation history is preserved across tool calls, allowing:
- Multi-step operations
- Error recovery
- Iterative refinement

### 3. Simplicity

- **No custom wrappers**: Uses standard LangGraph `ToolNode`
- **Natural flow**: `messages` works as LangGraph expects
- **Less code**: Simpler implementation, easier to maintain

### 4. LLM Provider Compatibility

The message sequence is carefully managed to comply with provider requirements:
- Mistral: No consecutive AIMessages
- OpenAI: Flexible message ordering
- Anthropic: Tool use patterns

### 5. Debugging and Auditing

- `messages`: Current node's focused context
- `message_history`: Complete audit trail
- Both available for inspection and logging

## Common Patterns

### Pattern 1: Node Handoff

```
Coder finishes → finish_task(summary="...")
                ↓
Tester starts → old messages preserved to message_history
                ↓
Tester's messages = [SystemMessage, HumanMessage with summary]
```

### Pattern 2: Tool Call Loop

```
Tester calls run_command → messages += [AIMessage, ToolMessage]
                         ↓
Tester calls run_command again → filtered messages used as context
                                ↓
messages = [SystemMessage, HumanMessage, ToolMessage, AIMessage, ToolMessage]
```

### Pattern 3: Error Recovery

```
Coder fails → finish_task(summary="Error: NPE in handler")
            ↓
Tester receives error summary → report_test_result(result="fail", summary="...")
                               ↓
Coder restarts → receives test failure summary in prompt
```

## Troubleshooting

### Issue: "Expected last role User or Tool but got assistant"

**Cause**: AIMessage followed by another AIMessage in the sequence.

**Solution**: This should not occur with the current architecture. Standard `ToolNode` automatically adds ToolMessages to `messages`, preventing consecutive AIMessages.

### Issue: Node loses context between tool calls

**Cause**: `messages` being cleared when it shouldn't be.

**Solution**: Check `is_node_switch` logic in `invoke_tool_node` - should only clear on actual node switch, not during tool call loops.

### Issue: Previous node summary not appearing

**Cause**: `agent_summary` not populated or template not rendering.

**Solution**:

1. Verify `record_finish_task_summary` is called
2. Check prompt template has `{% if agent_summary %}` block
3. Ensure `load_prompt` receives full `state` dict

### Issue: Message history not being preserved

**Cause**: `message_history` not being updated on node switch.

**Solution**: Verify that `invoke_tool_node` copies old `messages` to `message_history` when `is_node_switch` is true.

## Testing

The message handling system is validated by:

1. **Unit tests**: `tests/agent/services/test_message_processing.py`
2. **Integration tests**: `tests/agent/test_workflow.py`
3. **Manual testing**: Run agent with logging enabled to observe message flow

## Future Enhancements

Potential improvements:

1. **Message compression**: Summarize old messages to reduce token usage
2. **Selective history**: Include only relevant past interactions
3. **Cross-node references**: Allow nodes to reference specific past actions
4. **Message versioning**: Track message format changes over time
