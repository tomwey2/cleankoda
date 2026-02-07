---
description: Running and debugging the Coding Agent locally
---

# Local Running & Debugging Guide

This guide explains how to run or debug the Flask dashboard (`webapp`) and the LangGraph agent (`ai-coding-agent`) directly on your host machine while keeping Docker-based workbench semantics intact.

## 1. Prerequisites

1. Docker and Docker Compose installed (the workbench continues to run inside Docker).
2. Python 3.11+ with [uv](https://docs.astral.sh/uv/) installed locally.
3. `.env` populated with the same values used for the compose setup (copy `dotenv` → `.env`).
4. Workspace and instance folders created locally (`./workspace`, `./app/instance` by default).

## 2. Understand the Container/Host Split

- `docker-compose.yaml` always starts three containers: `webapp`, `ai-coding-agent`, and the workbench (e.g., `workbench-backend`).
- When you run the Python entry points locally, **stop the corresponding compose service first**. For example, to debug the Flask dashboard locally, bring down or stop the `webapp` container; to debug the LangGraph agent locally, stop `ai-coding-agent`.
- The workbench container keeps running in Docker. It must remain alive because shell commands and tests are executed there.
- The host and containers share identical directories via volumes:
  - `./workspace` ↔ `$WORKSPACE` inside both the agent and workbench containers.
  - `./app/instance` ↔ `/coding-agent/app/instance` for the SQLite database.
  This ensures that code edited or generated locally is immediately visible to the workbench.

## 3. Stopping Services Before Local Runs

```bash
docker compose stop webapp ai-coding-agent   # stop whichever service you plan to run locally
docker compose up -d workbench-backend       # ensure the workbench stays up (adjust name per stack)
```

> ⚠️ Do not leave both the containerized service and the local process running simultaneously—they will compete for the same ports (`5000` for webapp) and shared volumes.

## 4. Running the Flask Dashboard Locally

1. Export the same environment variables used in compose (the `.env` file is easiest):

   ```bash
   set -a
   source .env
   set +a
   ```

   Override paths if needed:

   ```bash
   export WORKSPACE=/home/you/path/to/workspace
   export INSTANCE_DIR=/home/you/path/to/instance
   ```

2. Install dependencies locally:

   ```bash
   uv sync
   ```

3. Run the Flask dashboard:

   ```bash
   uv run run_web.py
   ```

4. Navigate to [http://localhost:5000](http://localhost:5000).

#### Minimal VS Code `launch.json`

Place the following file under `.vscode/launch.json` to reuse the same settings when launching either entry point from VS Code:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Run Agent",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/run_agent.py",
            "console": "integratedTerminal",
            "envFile": "${workspaceFolder}/.env",
            "cwd": "${workspaceFolder}",
            "env": {
                "WORKSPACE": "${workspaceFolder}/workspace",
                "INSTANCE_DIR": "${workspaceFolder}/app/instance",
                "ENABLE_MCP_SERVERS": "false",
                "WORKBENCH": "workbench-backend-loc",
                "WORKBENCH_CODESPACE": "/coding-agent-workspace"
            }
        },
        {
            "name": "Python: Run Web",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/run_web.py",
            "console": "integratedTerminal",
            "envFile": "${workspaceFolder}/.env",
            "cwd": "${workspaceFolder}",
            "env": {
                "WORKSPACE": "${workspaceFolder}/workspace",
                "INSTANCE_DIR": "${workspaceFolder}/app/instance",
                "ENABLE_MCP_SERVERS": "false"
            }
        }
    ]
}
```

### Debugging the Dashboard (VS Code)

Use the `.vscode/launch.json` configuration named **"Flask Web"**. It mirrors the compose environment by setting `WORKSPACE`, `INSTANCE_DIR`, and `ENABLE_MCP_SERVERS`. Breakpoints inside `app/web/...` now trigger locally, while the workbench container handles build/test commands via shared volumes.

## 5. Running the LangGraph Agent Locally

1. Stop the `ai-coding-agent` container (see Section 3).
2. Reuse the same environment setup as above, ensuring `WORKBENCH` matches the container name from `docker-compose.yaml` (e.g., `workbench-backend`).
3. Launch the agent loop:

   ```bash
   uv run run_agent.py
   ```
   The agent will connect to the still-running workbench container (`docker ps` should show it) and share the `./workspace` volume, so file edits are synchronized automatically.

### Debugging the Agent (VS Code)

The `.vscode/launch.json` configuration named **"LangGraph Agent"** configures:
- `WORKSPACE` pointing to the shared folder (e.g., `../workspace1`).
- `INSTANCE_DIR` to reuse the same SQLite DB.
- `ENABLE_MCP_SERVERS=false` if you do not want helper MCP processes while debugging.

Set breakpoints anywhere in `app/agent/...`; VS Code attaches to the local Python process while Docker provides the workbench runtime.

## 6. Switching Between Backend and Frontend Workbenches

- Update `WORKBENCH` in your environment (or `.env`) to `workbench-frontend` to target the frontend container defined in `docker-compose.yaml`.
- If `AGENT_STACK` is unset, the runtime derives the stack from the suffix of the container name (`-backend`/`-frontend`).
- Remember to start the matching workbench container (`docker compose up -d workbench-frontend`).

## 7. Returning to Full Docker Mode

When local debugging is finished:

```bash
docker compose up -d webapp ai-coding-agent   # relaunch the services inside Docker
```

You can now stop the local Python processes. Because the volumes are identical, no file synchronization is required.
