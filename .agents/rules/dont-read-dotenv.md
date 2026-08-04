---
trigger: always_on
---

# RULE: Strict Environment Variable & Secret Protection

To maintain security and prevent sensitive credentials from leaking, you MUST adhere to the following rules regarding environment configuration:

1. **NEVER Read or Modify `.env` Files**:
   - You are strictly FORBIDDEN from reading, opening, scanning, editing, or inspecting the main `.env` file (or any `.env.local`, `.env.production`, or `.env.secret` files).
   - If a task requires checking or modifying environment variables, **STOP** and ask the user to make those specific changes manually, OR refer exclusively to template files.

2. **Use `.env.example` as Reference**:
   - ALWAYS use `.env.example` (or `.env.template` / `.env.dist`) to inspect available configuration keys, environment variables, default values, or required settings.
   - When introducing new features that require environment variables, add the placeholder/documentation exclusively to `.env.example`.

3. **Secret Hygiene**:
   - Never print, log, or hardcode secret keys, passwords, or tokens in terminal commands, code outputs, or response text.