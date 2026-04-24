---
name: generate-docstrings
description: Generates or refines Python docstrings and type hints. Focuses on Google-Style docstrings and creating LLM-friendly descriptions for LangChain tools.
---

# Generate Docstrings Skill

When asked to generate or update docstrings for Python functions, classes, or modules in this project, follow these guidelines meticulously. 

## 1. Style and Format
- **Format**: Always use the **Google Docstring Style**.
- **Completeness**: Include a clear summary, `Args:`, `Returns:`, and `Raises:` sections where applicable.
- **Type Hints**: Ensure the actual Python code uses strict type hints (`typing` module / Python 3.11+ built-in generics like `list[str]`). The docstring should match these type hints perfectly.

## 2. LLM-Friendly Tool Descriptions (CRITICAL)
If the function is a LangChain tool (e.g., decorated with `@tool` or placed in `src/agent/tools/`), the docstring has a special purpose: **It will be read by other LLM agents to understand how to use the tool.**
- Be extremely explicit about the **purpose** of the tool in the very first sentence.
- Explain **what inputs are expected** in the `Args` section in plain natural language so another LLM knows exactly how to format its inputs (e.g., "Must be a valid absolute file path").
- Describe the **output format** in the `Returns` section so the calling LLM knows what to expect (e.g., "Returns a JSON-formatted string containing the issue details").

## 3. Best Practices
- **Active Voice**: Use imperative mood ("Generate a summary...", not "Generates a summary...").
- **Conciseness**: Keep descriptions concise but informative. Do not state the obvious if the function name and type hints are self-explanatory, unless it's a tool for an LLM.
- **Pydantic**: For Pydantic models (common in `src/web/schemas/` or `src/core/config/`), add the description directly into the `Field(..., description="...")` parameter instead of just the class docstring, as this helps validation tooling and UI generation.

## How to Proceed
1. Review the provided source code.
2. Add or fix Python type hints if they are missing or incorrect.
3. Write the Google-style docstring.
4. Output the updated code snippet block.
