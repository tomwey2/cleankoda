---
name: architecture-review
description: Evaluates the project after major changes to ensure software architecture principles (MVC, clean architecture, LangGraph boundaries) are maintained and identifies areas for structural improvement.
---

# Architecture Review Skill

When invoked, your task is to evaluate the recent changes or a specific area of the codebase against the overarching software architecture requirements of the **CleanKoda** project. This is not a line-by-line code review, but a high-level structural analysis.

## Review Checklist

### 1. Separation of Concerns (MVC & Web Layer)
- **Routes vs. Services:** Do the Flask routes in `src/web/routes.py` contain business logic, or do they correctly delegate to `src/web/services/`? 
- **Mappers:** Are database models being passed directly into the UI, or are they being safely transformed by `src/web/mappers/` into schemas or dictionaries?
- **Data Access:** Is database interaction strictly contained within services or core utilities, avoiding raw SQL or ORM calls directly in routes or UI code?

### 2. The LangGraph Agent Architecture
- **Node Size:** Are the agent nodes in `src/agent/nodes/` becoming too large or monolithic? Can a node be split into smaller, more deterministic sub-nodes?
- **State Management:** Is the `AgentState` in `src/agent/state.py` becoming bloated? Are there variables that should be ephemeral (local to a node) rather than global in the state graph?
- **Tool Boundaries:** Are the LLM Tools (`src/agent/tools/`) pure functions without unnecessary side effects that could break the LangGraph execution flow?

### 3. Coupling and Dependencies
- **Layer Isolation:** Does the `src/core/` layer cleanly serve both `src/web/` and `src/agent/` without importing them back (preventing circular dependencies)?
- **Async vs. Sync:** Ensure an asynchronous operation does not mix with blocking synchronous calls (e.g., using `requests` inside an `async def` or mixing async and sync SQLAlchemy unnecessarily).

## How to execute

1. Analyze the holistic directory structure or the recently heavily modified files.
2. Point out specific architectural smells or boundary violations.
3. Do not just complain about the architecture—**propose a concrete refactoring pattern**. Show exactly which functions should be moved to which file or service to restore a clean architecture.
