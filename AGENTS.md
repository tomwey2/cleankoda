# Project Guidelines for CleanKoda

You are working on **CleanKoda**, an AI coding agent project. Please follow these guidelines meticulously.

## Tech Stack

- **Language:** Python 3.11+
- **Agent Framework:** LangChain, LangGraph
- **Web Framework:** Flask (with `async` support)
- **Database / ORM:** SQLAlchemy (via `flask-sqlalchemy`)
- **Validation:** Pydantic
- **Formatting / Linting:** `ruff` (line-length 100), `pylint`
- **Package Manager:** `uv` (`pyproject.toml`, `uv.lock`)
- **Testing:** `pytest`, `pytest-asyncio`
- **Docker:** Provided via `Dockerfile` and `docker-compose.yaml`

## Architecture & Directory Structure

The source code was recently refactored to the `src/` directory:
- `src/core/`: Application settings (`get_env_settings()`), unified utilities, database models, etc.
- `src/agent/`: LangGraph graphs, nodes, tools, state, and runtime environment logic.
- `src/web/`: Flask app creation (`create_app()`), routing, templates, request parsing, and web services.

## Style Guide & Best Practices

1. **Imports:**
   - Always use absolute imports referencing the `src` module (e.g., `from src.agent.utils import ...` instead of `from app...`).
   - Group imports logically (Standard Library -> Third Party -> Local/`src`).

2. **Typing & Validation:**
   - Use strict Python type hints throughout the codebase.
   - Use `Pydantic` for structured data validation, environment configuration (`EnvironmentSettings`), and structured LLM tool outputs if needed.

3. **Web Framework (Flask):**
   - Use Flask's `async` endpoint capabilities (`async def`) where logical (e.g., if you write network-bound routes).
   - Use `flask-sqlalchemy` properly within the application context. Ensure the DB extensions are initialized correctly in `src.core.extensions`.
   - Keep business logic in `services/` rather than within `routes.py`.

4. **Agent Workflows:**
   - Define deterministic workflows using LangGraph (`StateGraph`).
   - Agent logic should be modular (one function per node typically, held within `src/agent/nodes/`).
   - Wrap tools gracefully and provide precise docstrings, as LLMs will rely on tool descriptions.

5. **Tooling & Dependency Management:**
   - Do NOT use `pip` natively unless necessary. Use `uv run` and `uv add` to manage and invoke dependencies.
   - Example to run tests: `uv run pytest` or `uv run --with pylint -- pylint src/`.
   - Prefer updating `pyproject.toml` instead of `requirements.txt`.

6. **Environment Variables:**
   - Use `.env` and `.env-local` for configuration (do NOT commit `.env` and `.env-local`).
   - Never hardcode secrets. Always retrieve settings via the Pydantic config models in `src/core/config.py`.

## General Commit & Development Strategy

- Review all code changes to confirm no regressions are introduced (e.g., test changes matching imports).
- Ensure that the resulting code remains perfectly compatible with the existing architecture. 
- Ask clarifying questions before undertaking massive architectural changes.
