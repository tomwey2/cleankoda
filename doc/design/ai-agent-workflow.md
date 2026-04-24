### LangGraph Workflow
The system is built upon a stateful, multi-agent architecture powered by LangGraph. Instead of a monolithic process, the execution flow is intelligently orchestrated across specialized nodes. After successful test execution, the workflow routes through an Explainer node before Pull Request creation so that the generated PR body includes intent, reasoning, and verification context. The shared AgentState now carries `pr_description` for this handoff into PR creation.

![LangGraph Workflow](../images/workflow_graph.png)

* **Router Node:** The Routing workflows process inputs and then directs them to context-specific agents. It acts as the entry point. It analyzes the incoming ticket context and determines the optimal execution strategy by selecting the appropriate specialist. Additionally, the Router Node evaluates the complexity of the task and checks if the skill level of the agent is suitable for the task. This establishes the trust-first strategy, ensuring that agents are only assigned tasks they can handle effectively.

* **Specialist Nodes (Agents):**

  - **Coder:** Focuses on implementing new features and writing complex logic. This includes clean code strategies and a focus on modular, readable, and robust code. One specific form of this is **Bugfixer:**, who is specialized to fix errors with minimal changes to the codebase.

  - **Analyst:** Operates in read-only mode to perform code reviews, answer queries, or map out dependencies.

  - **Tester:** Executes unit tests in order to ensure the code is functioning as expected.

  - **Explainer:** Builds a structured PR description from the implementation plan plus the task-linked thought and tool-action history stored in SQLAlchemy (`AgentAction`). It uses `prompts/systemprompt_explainer.md` with the variables `plan`, `thoughts`, and `tools_used`, and intentionally does not consume git diff data in this MVP.

* **The Cognitive Loop** (Reasoning): The innermost circle. The agent "thinks," executes a tool (e.g., read), analyzes the output, and plans the next move. This is the classic **ReAct pattern** that makes complex problem-solving possible in the first place.

* **Self-Correction Loop** (Quality): This is where true reliability happens. Inspired by TDD (Test-Driven Development), our agent writes code, validates it against tests, and fixes its own bugs—before a human even sees the code. This is CleanKoda’s USP. It distinguishes rigorous Software Engineering from the current "Vibe Coding" approach.
