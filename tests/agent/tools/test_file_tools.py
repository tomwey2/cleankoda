from __future__ import annotations

import importlib
import sys
import types

import pytest

from app.core.config import set_env_settings


@pytest.fixture(scope="module", autouse=True)
def stub_langchain_tool_module():
    """Provide a minimal langchain_core.tools stub when dependency is missing."""

    if "langchain_core.tools" in sys.modules:
        yield
        return

    langchain_core_module = types.ModuleType("langchain_core")
    tools_module = types.ModuleType("langchain_core.tools")

    def tool_decorator(func):
        return func

    tools_module.tool = tool_decorator
    langchain_core_module.tools = tools_module
    sys.modules["langchain_core"] = langchain_core_module
    sys.modules["langchain_core.tools"] = tools_module

    try:
        yield
    finally:
        sys.modules.pop("langchain_core.tools", None)
        sys.modules.pop("langchain_core", None)


@pytest.fixture(name="list_files")
def list_files_fixture(stub_langchain_tool_module):
    """Import list_files after ensuring dependencies are available."""

    module = importlib.import_module("app.agent.tools.file_tools")
    importlib.reload(module)
    # Handle both stub and real langchain_core
    list_files_tool = module.list_files
    if hasattr(list_files_tool, 'func'):
        return list_files_tool.func
    return list_files_tool


@pytest.fixture(name="workspace_dir")
def workspace_dir_fixture(tmp_path, monkeypatch):
    """Provide an isolated workspace directory for file tool tests."""

    workspace = str(tmp_path / "workspace")
    import os
    os.makedirs(workspace, exist_ok=True)
    monkeypatch.setenv("WORKSPACE", workspace)
    set_env_settings(None)
    yield workspace
    set_env_settings(None)


def test_list_files_returns_relative_paths_and_skips_git(workspace_dir, list_files):
    """list_files should return only workspace-relative files and skip .git entries."""

    import os
    
    result1 = list_files()
    print(result1)
    
    # Create test files
    with open(os.path.join(workspace_dir, "file1.txt"), "w", encoding="utf-8") as f:
        f.write("hello")
    
    nested_dir = os.path.join(workspace_dir, "nested")
    os.makedirs(nested_dir, exist_ok=True)
    with open(os.path.join(nested_dir, "file2.txt"), "w", encoding="utf-8") as f:
        f.write("world")

    git_dir = os.path.join(workspace_dir, ".git")
    os.makedirs(git_dir, exist_ok=True)
    with open(os.path.join(git_dir, "ignored.txt"), "w", encoding="utf-8") as f:
        f.write("ignored")

    result = list_files()
    assert sorted(result.splitlines()) == ["file1.txt", "nested/file2.txt"]


def test_list_files_denies_access_outside_workspace(workspace_dir, list_files):
    """list_files should not allow traversing outside the configured workspace."""

    assert list_files("../../etc") == "Access denied"


def test_list_files_returns_no_files_message_for_empty_directory(workspace_dir, list_files):
    """Empty directories should report that no files were found."""

    import os
    empty_dir = os.path.join(workspace_dir, "empty")
    os.makedirs(empty_dir, exist_ok=True)

    assert list_files("empty") == "No files found."
