# Issue Tracking System
## States
In an issue tracking system, an issue goes through several states: `Todo`, `In Progress`, `In Review`, and `Done`.

It can change these states through agent actions or human intervention, as shown in the following diagram.

```mermaid
stateDiagram-v2
    [*] --> Todo : Human
    Todo --> InProgress : Agent
    InProgress --> InReview : Agent
    InReview --> [*]: Human
    InReview --> InProgress : Human
    InReview --> Todo : Human
```

## Human in the Loop
The agent and the human work together to complete the issue. The agent has an executing role, while the human has a monitoring and controlling role.

- Backlog --> Todo: The human adds the issue to the Todo column when it is to be processed by the agent.

- Todo --> In Progress: The agent takes the issue and works on it.

- In Progress --> In Review: The agent has finished its work and hands it off to the human.

- In Review --> In Progress: The human reviews the result, provides feedback, and returns the issue to the agent for further processing.

- In Review --> Todo: The human wants the agent to restart the issue.

- In Review --> Done: The result is satisfactory; the human completes the issue.

## Resuming the active issue
The issue remains active beyond the workflow cycle. Therefore, it is important that when a new agent cycle starts, the last processed issue is resumed, provided it still exists. Only when it no longer exists can a new issue be processed.

```mermaid
flowchart TD
    A@{ shape: lean-r, label: "issue-id from db" }
    A --> M{issue-id None?}
    M --> |yes|C
    M --> |no|K[get issue with issue-id from issue tracking system]
    K --> B{exist issue?}
    B --> |yes| E{in review?}
    B --> |no| C[get new issue with state 'todo' from issue tracking system]
    C --> G{exist issue?}
    G --> |yes| D[save issue in db]
    G --> |no| Z
    D --> H[delete plan.md]
    H --> Y@{shape: lean-r, label: "{'issue': issue}"}
    E -->|yes| Z@{shape: lean-r, label: "{'issue': None}"}
    E -->|no| F{in progress?}
    F -->|yes| Y
    F -->|no| C
```
