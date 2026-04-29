# Environment Settings Architecture

This document explains the centralized environment settings system and how to use it.

## Overview

The application uses a centralized `EnvironmentSettings` dataclass to manage all environment variable access. This provides:

- **Type safety**: All settings are typed and validated
- **Testability**: Easy to inject mock settings in tests
- **Lazy initialization**: Settings loaded only when first accessed
- **Clear validation**: Explicit error messages when required settings are missing
- **Single source of truth**: One place to see all environment variables

## Architecture

### Core Components

1. **`EnvironmentSettings` dataclass** (`app/core/environment_settings.py`)
   - Frozen dataclass containing all environment variables
   - Factory method `from_env()` to load from environment
   - Validation helper methods for use-time checks

2. **Lazy initialization** (`app/core/config.py`)
   - `get_env_settings()` - Returns settings, initializing on first call
   - `set_env_settings()` - Override settings (primarily for testing)

3. **Test fixtures** (`tests/conftest.py`)
   - Autouse fixture that sets minimal test settings
   - Resets settings between tests

## Usage Patterns

### Basic Usage

```python
from app.core.config import get_env_settings

def my_function():
    settings = get_env_settings()
    workspace = settings.workspace
    # Use workspace...
```

### With Validation

When your code requires specific settings, use validation helpers:

```python
from app.core.config import get_env_settings


### Caching Settings in Functions

For functions that access settings multiple times, cache the result:

```python
from app.core.config import get_env_settings

def complex_operation():
    env = get_env_settings()  # Cache locally
    
    workspace = env.workspace
    workbench = env.workbench
    
    # Use cached settings...
```

## Required vs Optional Settings

### Required at Startup

Only two settings are required when the application starts:

- `ENCRYPTION_KEY` - Fernet encryption key for database encryption
- `WORKSPACE` - Path to the coding workspace directory

These are validated in `EnvironmentSettings.from_env()` and will raise `ValueError` if missing.

### Optional Settings

All other settings are optional and validated when used:

- `SECRET_KEY` - Flask secret key (default: development key)
- `DATABASE_URL` - Database connection URL (default: sqlite in instance/)
- `INSTANCE_DIR` - Flast instance Directory used for sqlite database (default: instance/)
- `WORKBENCH` - Docker container name that hosts the runnable workbench environment (e.g., `workbench-backend` or `workbench-frontend`). Defaults to empty, which requires docker-compose defaults.
- `WORKBENCH_WORKSPACE` - Path to workspace inside the workbench container where commands are executed. Defaults to the `WORKSPACE` value if not set. This allows separating the agent's workspace path from the container's execution path.
- `AGENT_STACK` - Optional override for the runtime technology stack. Accepts `backend` or `frontend`. When unset or invalid, the stack is derived automatically from the `WORKBENCH` name.
- `GITHUB_REPO_URL` - Default GitHub repository URL (default: empty)
- `ENABLE_MCP_SERVERS` - Enable MCP servers (default: `true`)
- `LOGGING_CONFIG_FILE` - Path to an external logging configuration file (`.json` or `.ini`). When set, overrides the built-in default logging setup. See [Logging](./logging.md) for details.
- `LLM_CALLS_PER_SECOND` - Optional rate limit for LLM calls. Set to a positive float to cap how many tool-call attempts are sent to the LLM each second (default: `0`, which means unlimited). Useful when working with providers that enforce strict QPS limits.

When `LLM_CALLS_PER_SECOND` is configured, the shared `invoke_tool_node` helper delays each LLM invocation just enough to keep the average call rate at or below the configured value. This guard applies to every tool-based node (coder, analyst, tester, bugfixer) and is enforced per worker process. Leave the value at `0` to keep the existing behavior with no throttling.

## Workspace Path Configuration

The application distinguishes between two workspace paths to support different deployment scenarios:

### `WORKSPACE` (Agent Workspace)
- **Purpose**: Path where the AI agent operates and manages files
- **Location**: May be a host path when running locally, or a container path in Docker
- **Used by**: File operations, code generation, and agent file system access
- **Example**: `/home/user/.local/workspace` (local) or `/coding-agent-workspace` (Docker)

### `WORKBENCH_WORKSPACE` (Container Workspace)
- **Purpose**: Path where commands are executed inside the workbench container
- **Location**: Always a path inside the Docker workbench container
- **Used by**: `bash` tool for executing shell commands
- **Default**: Falls back to `WORKSPACE` value if not explicitly set
- **Example**: `/coding-agent-workspace`

### Path Translation

The `bash` tool automatically translates agent workspace paths to container workspace paths:

```python
# LLM generates command with agent workspace:
"cd /home/user/.local/workspace && mvn clean test"

# bash translates to container workspace:
"cd /coding-agent-workspace && mvn clean test"
```

This allows the same agent code to work both locally and in Docker without modification.

### Configuration Examples

**Docker Development (docker-compose.yaml):**
```yaml
environment:
  - WORKSPACE=/coding-agent-workspace
  - WORKBENCH_WORKSPACE=/coding-agent-workspace
```

**Local Development (.env):**
```bash
WORKSPACE=/home/user/.local/workspace
WORKBENCH_WORKSPACE=/coding-agent-workspace
```

## Validation Helper Methods

### `require_encryption_key() -> str`

Validates that encryption key is configured. Usually not needed since it's required at startup.

```python
key = settings.require_encryption_key()
```

**Raises:** `ValueError` if `ENCRYPTION_KEY` is not set.

### `require_llm_api_key(provider: str) -> str`

Validates that API key for specific LLM provider is configured.

```python
# For OpenAI
api_key = settings.require_llm_api_key("openai")

# For Mistral
api_key = settings.require_llm_api_key("mistral")

# For Google/Gemini
api_key = settings.require_llm_api_key("google")
```

**Supported providers:** `openai`, `mistral`, `google`, `openrouter`, `anthropic`, `ollama`

**Raises:** `ValueError` if the provider's API key is not set.

### `get_api_key(env_var_name: str) -> str`

Legacy method that returns API key by environment variable name. Returns empty string if not set (for backward compatibility).

```python
key = settings.get_api_key("OPENAI_API_KEY")
```

**Note:** Prefer `require_llm_api_key()` for new code as it provides better error messages.

## Adding New Environment Variables

To add a new environment variable:

1. **Add field to `EnvironmentSettings` dataclass:**

```python
@dataclass(frozen=True)
class EnvironmentSettings:
    # ... existing fields ...
    
    # Add your new field
    my_new_setting: Optional[str] = None
```

2. **Load in `from_env()` method:**

```python
@classmethod
def from_env(cls) -> EnvironmentSettings:
    # ... existing code ...
    
    return cls(
        # ... existing fields ...
        my_new_setting=os.environ.get("MY_NEW_SETTING"),
    )
```

3. **Add validation helper if required:**

```python
def require_my_new_setting(self) -> str:
    """Get my new setting or raise if not configured."""
    if not self.my_new_setting:
        raise ValueError(
            "MY_NEW_SETTING is required for this operation. "
            "Set the MY_NEW_SETTING environment variable."
        )
    return self.my_new_setting
```

4. **Update documentation:**
   - Add to the "Optional Settings" list above
   - Document in `.env.example` if applicable
   - Add to testing guide if relevant

## Design Decisions

### Why Lazy Initialization?

Lazy initialization (via `get_env_settings()`) instead of module-level initialization solves several problems:

1. **Tests can inject settings** before any code tries to read them
2. **Import order doesn't matter** - settings loaded when first accessed
3. **Clear dependency** - function call makes it obvious settings are being accessed
4. **Testable** - can reset and override settings between tests

### Why Optional GITHUB_TOKEN?

Making `GITHUB_TOKEN` optional (validated at use time) allows:

1. **Tests without GitHub** to run without a token
2. **Features that don't use GitHub** to work independently
3. **Better error messages** - validation happens where the token is actually needed
4. **Graceful degradation** - app can start even if GitHub is unavailable

### Why Frozen Dataclass?

The `frozen=True` parameter makes `EnvironmentSettings` immutable:

1. **Thread-safe** - no risk of concurrent modification
2. **Predictable** - settings don't change during execution
3. **Testable** - must explicitly override via `set_env_settings()`

## Migration Guide

## Common Pitfalls

### Don't Cache Settings Globally

**Bad:**
```python
from app.core.config import get_env_settings

# DON'T DO THIS - caches at module level
SETTINGS = get_env_settings()

def my_function():
    return SETTINGS.workspace
```

**Good:**
```python
from app.core.config import get_env_settings

def my_function():
    # DO THIS - call function each time
    settings = get_env_settings()
    return settings.workspace
```

**Why:** Global caching prevents tests from overriding settings.

### Don't Access Settings at Module Level

**Bad:**
```python
from app.core.config import get_env_settings

# DON'T DO THIS - runs at import time
settings = get_env_settings()
WORKSPACE = settings.workspace

def my_function():
    return WORKSPACE
```

**Good:**
```python
from app.core.config import get_env_settings

def my_function():
    # DO THIS - access when function is called
    settings = get_env_settings()
    return settings.workspace
```

**Why:** Module-level access defeats lazy initialization.

### Don't Silently Ignore Missing Settings


## See Also

- [Testing Guide](./TESTING_ENVIRONMENT_SETTINGS.md) - How to test with environment settings
- [Flask Configuration](https://flask.palletsprojects.com/en/2.3.x/config/) - Flask's config system
- [Twelve-Factor App](https://12factor.net/config) - Configuration best practices
