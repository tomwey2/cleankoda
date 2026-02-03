# AI Agent Message Stack Specification

## Overview

This document describes the message stack structure used by the AI coding agent. The stack ensures compatibility with LLM APIs (particularly Mistral) while maintaining conversation context and enabling tool-based interactions.

## Message Types

| Type | Role | Purpose |
|------|------|---------|
| **SystemMessage** | `system` | Role instructions, injected fresh per node |
| **HumanMessage** | `user` | User requests, corrections, feedback |
| **AIMessage** | `assistant` | AI responses, tool calls, acknowledgments |
| **ToolMessage** | `tool` | Tool execution results |

## Stack Structure

### Per-Node Construction

Each node that calls the LLM constructs messages as:

```
[SystemMessage(role-specific)]  ← Fresh for each node invocation
    ↓
[Filtered conversation history]  ← Preserved context from state
```

The `filter_messages_for_llm()` function ensures:
- **System messages** from history are preserved at start
- **First HumanMessage** (first non-System message) is the task context anchor
- **Recent messages** are limited to `max_messages` count
- **Tool call/response pairs** are never split by filtering
- **No HumanMessage found** → logs warning and returns entire stack unchanged

### Conversation Flow

#### Successful Tool Call
```
[System: "You are coder..."]
[Human: "Implement feature X"]
[AI: tool_calls=[write_file]]
[Tool: "File written"]
[AI: tool_calls=[finish_task]]  ← Node ends with tool call
```

#### Retry on Invalid Response
```
[System: "You are coder..."]
[Human: "Implement feature X"]
[AI: ""]  ← Invalid: no tool_calls (not added to state)
    ↓ (retry in same node)
[AI: ""]  ← Added to current_messages for context
[Human: "ERROR: Invalid response. You MUST call a tool!"]
[AI: tool_calls=[write_file]]  ← Valid response
```

## Validation Rules

### 1. Response Validation (Per Node)

AI responses **must** contain `tool_calls`:

```python
has_tool_calls = bool(getattr(response, "tool_calls", []))

if has_tool_calls:
    return success  # Valid - ends with tool call
else:
    retry_with_correction()  # Invalid - add correction and retry
```

**No text-only responses are accepted.** Content in `response.content` is ignored for validation.

### 2. Invalid Response Handling

When AI returns no tool_calls:

1. **Add invalid response** to `current_messages` so AI sees its mistake
2. **Add HumanMessage correction** with clear error and instruction
3. **Escalate** `tool_choice` from `"auto"` to `"any"` (force tool use)
4. **Retry** up to 3 attempts

```python
current_messages.append(response)  # The invalid response
current_messages.append(
    HumanMessage(content="ERROR: Invalid response. You MUST call a tool!")
)
```

### 3. State Updates

Valid responses are added to agent state:

```python
return {
    "messages": [response],  # Appended to state by LangGraph
    "current_node": "coder",
}
```

## Filtering Behavior

### `filter_messages_for_llm(messages, max_messages=10)`

**Purpose:** Prepare conversation history for LLM while maintaining valid stack.

**Rules:**

1. **System messages** → Kept at start (from history)
2. **First HumanMessage** → Always preserved (first non-System message, typically the task)
3. **Recent messages** → Last `max_messages - 1` after first human
4. **Tool pairs preserved** → If window starts at ToolMessage, extends back to include its AIMessage (valid input assumed)
5. **No empty trailing AI** → AIMessages with no content AND no tool_calls are removed
6. **No HumanMessage found** → Logs warning, returns entire stack unchanged

**Example with `max_messages=4`:**

```
Input:  [System] + [Task] + [AI1] + [Human1] + [AI2] + [Human2] + [AI3] + [Human3]
Output: [System] + [Task] + [AI3] + [Human3]
              ↑      ↑        ↑        ↑
         preserved  first   recent   recent
                   human
```

## Stack Validity Rules

The stack is **valid** when:

1. Ends with HumanMessage, ToolMessage, or AIMessage with tool_calls
2. Every ToolMessage has a preceding AIMessage with matching tool_call_id
3. No orphaned tool calls (AIMessage with tool_calls has subsequent ToolMessages)

The stack is **invalid** when:

1. Ends with empty AIMessage (no content, no tool_calls)
2. ToolMessage without preceding AIMessage with matching tool_call
3. AIMessage with tool_calls not followed by required ToolMessages

## Implementation Notes

- **task_fetch_node** injects task as **HumanMessage** (not SystemMessage)
- **Each node** has its own SystemMessage defining its role
- **filter_messages_for_llm** only filters, never fixes invalid stacks
- **Caller responsibility** to ensure valid stack before filtering
