# Message Handling Architecture

## Overview

The agent uses a dual-message system to maintain both global conversation history and per-node message stacks. This architecture ensures clean context for each LLM node while preserving the complete interaction history.

## Message Fields in AgentState

### 1. `messages` (Global History)

- **Type**: `Annotated[list[BaseMessage], add_messages]`
- **Purpose**: Complete conversation history across all nodes
- **Scope**: Entire agent execution lifecycle
- **Usage**: Audit trail, debugging, full context preservation

### 2. `node_messages` (Per-Node Stack)

- **Type**: `Annotated[list[BaseMessage], add_messages]`
- **Purpose**: Isolated message stack for each LLM node (analyst, coder, tester)
- **Scope**: Single node execution, reset on node switch
- **Usage**: LLM context for current node operations

## Message Flow

### Node Switch (e.g., coder → tester)

When switching between nodes:

1. **Detection**: `state.get("current_node") != node_name` in `invoke_tool_node`
2. **Reset**: `node_messages` is cleared
3. **Initialization**: New stack starts with:
   ```python
   [
       SystemMessage(content=system_prompt),
       HumanMessage(content=human_prompt)  # includes previous node summary
   ]
   ```
4. **Previous Node Summary**: The `human_prompt` is rendered from templates (e.g., `prompt_testing.md`) and includes `agent_summary` entries from the previous node

### Tool Call Loop (same node)

When a node makes multiple tool calls:

1. **Detection**: `state.get("current_node") == node_name`
2. **Preservation**: Existing `node_messages` are retained
3. **Filtering**: `filter_messages_for_llm` applied to keep recent context
4. **Accumulation**: New messages added to stack:
   ```python
   [
       SystemMessage(content=system_prompt),
       HumanMessage(content=human_prompt),
       ...filtered_existing_node_messages,
       AIMessage(with tool_calls),
       ToolMessage(tool results)
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
    # Tool call loop: preserve and filter existing node_messages
    existing_node_messages = state.get("node_messages", [])
    filtered_messages = filter_messages_for_llm(
        existing_node_messages, max_messages=max_messages
    )
    current_messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ] + filtered_messages
```

**Returns**:
```python
{
    "messages": [response],        # Global history
    "node_messages": [response],   # Per-node stack
    "current_node": node_name,
    ...
}
```

### Custom ToolNode Wrapper (`app/agent/graph.py`)

Standard `ToolNode` only updates `messages`. Our wrapper also updates `node_messages`:

```python
def _create_tool_node_with_node_messages(tools: list):
    base_tool_node = ToolNode(tools)
    
    def tool_node_wrapper(state: AgentState):
        result = base_tool_node.invoke(state)
        tool_messages = [
            msg for msg in result.get("messages", []) 
            if isinstance(msg, ToolMessage)
        ]
        
        return {
            "messages": result.get("messages", []),
            "node_messages": tool_messages,  # Add to per-node stack
        }
    
    return tool_node_wrapper
```

**Why needed**: Ensures ToolMessages are added to `node_messages` so the next LLM call has the correct context.

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

- **Does NOT use** `node_messages`
- Uses structured output with minimal context (`max_messages=3`)
- Only reads from global `messages` for routing decisions

### Analyst, Coder, Tester Nodes

- **Use** `node_messages` for LLM context
- **Receive** previous node summaries via prompt templates
- **Maintain** isolated conversation stacks during tool call loops

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

### 3. LLM Provider Compatibility

The message sequence is carefully managed to comply with provider requirements:
- Mistral: No consecutive AIMessages
- OpenAI: Flexible message ordering
- Anthropic: Tool use patterns

### 4. Debugging and Auditing

- `messages`: Complete audit trail
- `node_messages`: Current node's focused context
- Both available for inspection and logging

## Common Patterns

### Pattern 1: Node Handoff

```
Coder finishes → finish_task(summary="...")
                ↓
Tester starts → receives summary in prompt
                ↓
Tester's node_messages = [SystemMessage, HumanMessage with summary]
```

### Pattern 2: Tool Call Loop

```
Tester calls run_command → node_messages += [AIMessage, ToolMessage]
                         ↓
Tester calls run_command again → filtered node_messages used as context
                                ↓
node_messages = [SystemMessage, HumanMessage, ToolMessage, AIMessage, ToolMessage]
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

**Solution**: Ensure ToolNode wrapper adds ToolMessages to `node_messages`.

### Issue: Node loses context between tool calls

**Cause**: `node_messages` not being preserved in tool call loops.

**Solution**: Check `is_node_switch` logic in `invoke_tool_node`.

### Issue: Previous node summary not appearing

**Cause**: `agent_summary` not populated or template not rendering.

**Solution**: 
1. Verify `record_finish_task_summary` is called
2. Check prompt template has `{% if agent_summary %}` block
3. Ensure `load_prompt` receives full `state` dict

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
