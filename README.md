# cleankoda

`cleankoda` is a terminal-based AI coding agent for clean code software development. It features a full TUI (Terminal User Interface) with multi-provider LLM support, interactive tool execution (listing files, reading/writing files, running shell commands), secure credentials management, and isolated Docker sandbox environments.

## Features

- **Multi-Provider LLM Support (LiteLLM)**: Seamlessly switch between **Mistral**, **OpenAI**, **Anthropic**, **Ollama**, and **Google Gemini**.
- **Interactive TUI & Reactive Session State**: Rich terminal interface powered by `prompt-toolkit` with scrollable message history and a reactive status line. Session and agent states are consolidated in `SessionState` with an Observer pattern (`subscribe` / `notify`) for instant UI updates.
- **TDD Implementation Planning & Step-by-Step Execution (`/plan`, `/execute`, `/abort`)**: Create structured TDD implementation plans saved under `.cleankoda/plans/` and execute them step-by-step. Features an atomic `PlanManager` for checkbox tracking (`- [ ]` -> `- [x]`) and Human-in-the-Loop (HITL) review states (`REVIEWING_PLAN` and `REVIEWING_CODE`) with dynamic action hints on status line 2. Supports free-text feedback routing for iterative plan refinement or code corrections, and `/abort` to discard plans or pause execution.
- **Universal Output Pruning & Robust Tooling**: Language-agnostic output pruning for shell tool executions with a 120-second default timeout, retaining essential error tracebacks and test summaries while enforcing an 8,000-character hard limit per output stream.
- **Issue Tracking Integration (`/issue`)**: Bind active ITS tickets and user stories directly into the system prompt context for targeted feature development.
- **Isolated Docker Sandbox**: Execute shell commands safely inside containerized Docker environments (`python:3.11-slim`, `python:3.12-slim`, `node:20-slim`, `rust:latest`, `golang:1.22`, `ubuntu:24.04`) with strict resource limits (`mem_limit="2g"`, max 2 CPUs, disabled network access) or switch to direct host execution. Automatic asynchronous container launch on TUI and Headless startup.
- **Interactive Tool Execution**: Support for tool calling in both TUI streaming and Headless modes for directory listing, file inspection, file modification, and shell command execution (with user approval).
- **Secure Credentials Store**: Secure storage for provider API keys (`~/.config/cleankoda/credentials.json` with `0o600` file permissions) managed interactively via `/provider`.
- **Headless & Scripting Mode**: Non-interactive execution for automated scripts, CI/CD pipelines, and shell pipes.
- **Extensible Command Registry**: Interactive modal dialogs and slash command dispatch system (`/issue`, `/plan`, `/execute`, `/abort`, `/provider`, `/model`, `/sandbox`, `/temp`, `/help`, `/clear`, `/exit`).
- **Persistent Memory & Logging**: Automatic conversation tracking and structured JSON logging.

## Tech Stack

- **Python** (`>= 3.11`)
- **[Prompt Toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit)**: Terminal User Interface (TUI) layout, keybindings, and interactive modal dialogs.
- **[Rich](https://github.com/Textualize/rich)**: Rich text formatting and terminal output styling.
- **[LiteLLM](https://github.com/BerriAI/litellm)**: Multi-provider LLM integration (Mistral, OpenAI, Anthropic, Ollama, Google Gemini) and tool call streaming.
- **[Docker SDK for Python](https://docker-py.readthedocs.io/)**: Isolated sandbox container lifecycle management and command execution environment.

---

## Getting Started

### Prerequisites

- **Python**: `>= 3.11`
- **Package Manager**: [`uv`](https://github.com/astral-sh/uv) (recommended)
- **API Key(s)**: An API key for your chosen provider (e.g. OpenAI, Anthropic, Mistral, Google Gemini) or a local [Ollama](https://ollama.com/) instance.
- **Docker**: (Optional) Required if you want to run shell commands in an isolated Docker sandbox environment.

### Setup

1. **Install the tool**:
   Download the code of this repository and install the tool with the following `uv` command:
   ```bash
   uv tool install .
   ```
   Then cleankoda cli is installed in the folder `~/.local/bin` (Linux) and it can be used system wide. 

### Usage

#### Running the TUI Application

To launch `cleankoda` with the interactive terminal interface, go to your project folder and run:

```bash
cleankoda
```

#### Headless Mode (Scripting & CI/CD)

`cleankoda` supports non-interactive execution, ideal for scripts, automated pipelines, or piping text:

- **Positional Prompt Argument**:
  ```bash
  cleankoda "Explain the main function in src/cleankoda/tui.py"
  ```

- **Prompt Flag (`-p` / `--prompt`)**:
  ```bash
  cleankoda -p "Generate a unit test for memory.py"
  ```

- **Piped Standard Input**:
  ```bash
  cat src/cleankoda/tui.py | cleankoda "Review this file for potential bugs"
  ```

- **Force Execution Mode Flags**:
  - `--headless`: Explicitly force non-interactive headless execution.
  - `--tui`: Explicitly force interactive TUI mode.

---

### Slash Commands (Command Registry)

`cleankoda` includes an extensible command registry. Slash commands work in both TUI mode and Headless mode:

- **`/issue`**: View or select the active ticket/issue context from the Issue Tracking System.
- **`/plan`** or **`/plan [goal]`**: Create a step-by-step TDD implementation plan for the active issue saved under `.cleankoda/plans/plan_<safe_title>_<id>.md`. Enters state `REVIEWING_PLAN` with interactive prompt for feedback/refinement.
- **`/execute`** or **`/execute all`**: Execute open implementation plan tasks step-by-step with automatic checkbox updates (`- [x]`) and Human-in-the-Loop (HITL) review pauses (`REVIEWING_CODE`) at phase boundaries or after single steps displaying compact Git status and diff summaries.
- **`/abort`**: Abort the active review state or execution loop. In `REVIEWING_PLAN`, discards the generated plan file. In `REVIEWING_CODE`, pauses execution while preserving completed task checkboxes (`[x]`).
- **`/sandbox`** or **`/sandbox [off|image_name]`**: Open an interactive selection modal to configure the execution environment. 
- **`/provider`** or **`/provider <name>`**: Open an interactive selection modal to switch LLM providers (Mistral, OpenAI, Anthropic, Ollama, Google Gemini) and prompt for API keys when required. Automatically switches the model to the primary default model for that provider.
- **`/model`** or **`/model <name>`**: Open an interactive selection modal (filtered for the current provider) or set a specific model.
- **`/temp`** or **`/temp <value>`**: View or adjust the LLM sampling temperature (e.g. `/temp 0.2`).
- **`/help`**: Display available commands and their descriptions.
- **`/clear`**: Clear current message memory and start a fresh context.
- **`/exit`** (aliases: `/quit`, `/q`): Exit the application.
