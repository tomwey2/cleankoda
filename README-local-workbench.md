# Local Workbench Scripts

The local workbench scripts have been moved to the `.local/` directory for better organization.

## Quick Start

```bash
# Start the local workbench
./.local/workbench-backend-local.sh start

# Enter the container
./.local/workbench-backend-local.sh exec

# Stop the workbench
./.local/workbench-backend-local.sh stop
```

## Files in `.local/` Directory

- **`workbench-backend-local.sh`** - Main script to run the local workbench
- **`README-workbench-local.md`** - Comprehensive documentation
- **`example-workflow.sh`** - Example usage workflow
- **`workspace/`** - Default workspace directory (created automatically)

## Default Workspace

The workspace is now located at `.local/workspace/` by default, keeping all workbench files organized in the `.local/` directory.

## Full Documentation

See `.local/README-workbench-local.md` for complete documentation, including:
- Prerequisites
- All available commands
- Environment variables
- Troubleshooting guide
- Comparison with Docker Compose

## Example Usage

```bash
# Run the example workflow
./.local/example-workflow.sh

# Or manually step by step
docker compose up cleancoda-docker-host -d
./.local/workbench-backend-local.sh start
./.local/workbench-backend-local.sh exec mvn --version
./.local/workbench-backend-local.sh stop
```
