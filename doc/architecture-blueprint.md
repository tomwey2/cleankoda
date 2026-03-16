# Architecture Blueprint: Serverless CleanKoda on Google Cloud Run
This document describes the final, scalable serverless architecture for CleanKoda on the Google Cloud Platform (GCP). It solves the problem of the lack of shared disks in the cloud, enables seamless customer onboarding, and optimizes runtime costs through intelligent event routing ("scale-to-zero").

## 1. GCP Products at a Glance
Although we operate entirely serverless, we use two different Google Cloud deployment models for the frontend (dashboard/gateway) and the agent (worker with workbench):

### 1. The Flask App (frontend/gateway) -> Google Cloud Run Service
- Why this product? A "service" is designed to respond to incoming web traffic (HTTP requests). It wakes up in milliseconds, delivers the dashboard, accepts webhooks, and automatically scales to multiple instances when there are many visitors.

### 2. The Agent (worker/fat image) -> Google Cloud Run Job
- Why this product? A "job" does not listen for web traffic. It is designed for asynchronous AI tasks. A job can run for hours and terminates completely autonomously ("fire and forget") once it has finished its work.

## 2. The Intelligent API Gateway & Event Trigger (Shift-Left)
To prevent resource-intensive AI agents from running into a void, the stateless Flask app acts as an intelligent gatekeeper. We move the pure check logic ("Is there work?") to the cost-effective frontend. The worker job is only started if there is actual work available at that precise moment.

We use two automated triggers for this:

### Trigger: Smart Polling via Cloud Scheduler (e.g., Jira)
Since enterprise customers are reluctant to allow internal Jira webhooks through firewalls, we use an asynchronous pull model.

- Google Cloud Scheduler (a serverless cron job) periodically calls a protected route in the Flask app.
- Shift Left: Flask makes a tiny, lightning-fast API call to the ticketing system (Jira/Trello). If there are no new tickets in the CleanKoda column, Flask responds with 200 OK. The resource-intensive worker job is not triggered (cost: €0).
- If the ticket's status changes, Flask assigns the event to the tenant and immediately fires a targeted worker job that starts the agent.
- Smart Scheduling: To avoid unnecessary API calls at night or on weekends, the scheduler runs according to the customer's defined working hours (e.g., Mon-Fri, 8:00 AM - 6:00 PM via cron syntax */5 8-18 * * 1-5).

The same applies to GitHub: If the status of a pull request changes (e.g., if a human developer adds a comment to the pull request, such as "Please make the button red"), the agent is called.

### Technical Implementation in Code (Flask Backend - Hybrid Setup)
Flask spawns the worker as soon as actual work has been validated. This is where our hybrid strategy comes into play: The gateway dynamically decides, via an environment variable (DEPLOYMENT_MODE), whether the agent is started via the Google API (SaaS) or via the local Docker environment (on-premises).

```python
import os
import docker
from google.cloud import run_v2

def spawn_agent_worker(project_id, region, target_language, ticket_id, repo_url, tenant_id, pr_feedback=None):
    """
    Main router: Decides how the agent is started based on the environment variable.
    """
    mode = os.environ.get("DEPLOYMENT_MODE", "SERVERLESS")
    
    # Common environment variables for the agent
    env_vars = {
        "TICKET_ID": ticket_id,
        "REPO_URL": repo_url,
        "TENANT_ID": tenant_id,
        "DEPLOYMENT_MODE": mode
    }
    if pr_feedback:
        env_vars["PR_FEEDBACK"] = pr_feedback

    # Routing to the corresponding start logic
    if mode == "SERVERLESS":
        return _spawn_gcp_cloud_run_job(project_id, region, target_language, env_vars)
    elif mode == "ON_PREMISE":
        return _spawn_local_docker_container(target_language, env_vars)
    else:
        raise ValueError(f"Unbekannter DEPLOYMENT_MODE: {mode}")


def _spawn_gcp_cloud_run_job(project_id, region, target_language, env_vars):
    """
    Option A (Serverless): Spawn an asynchronous Cloud Run Job via the Google API.
    """
    client = run_v2.JobsClient()
    job_name = f"cleankoda-agent-{target_language}"
    job_path = client.job_path(project_id, region, job_name)

    # Formatting variables for the GCP API
    gcp_env_vars = [{"name": k, "value": str(v)} for k, v in env_vars.items()]

    request = run_v2.RunJobRequest(
        name=job_path,
        overrides={"container_overrides": [{"env": gcp_env_vars}]}
    )

    # Start job (“Fire and Forget”)
    operation = client.run_job(request=request)
    return operation.operation.name


def _spawn_local_docker_container(target_language, env_vars):
    """
    Option B (On-Premise): Spawn a local Docker container using the Docker SDK.
    """
    client = docker.from_env()
    image_name = f"cleankoda-agent-{target_language}:latest"
    
    # Container über den lokalen Docker-Daemon starten
    container = client.containers.run(
        image=image_name,
        environment=env_vars,
        detach=True,
        remove=True # Wichtig: Container löscht sich nach der Arbeit selbst!
    )
    return container.id
```

## 3. The Worker: The "Fat Image" Pattern
Since Cloud Run jobs are isolated and do not share disks with other containers, **the agent** (LangGraph) and **the workbench** (programming environment, e.g., Java/Maven) must reside in the same Docker container. We build a specific base image for each target language.

Example: `Dockerfile.java`

```dockerfile
  # 1. The Official Python Image
  FROM python:3.11-slim

  # 2. The Workbench: Install Java 17, Maven and Git
  RUN apt-get update && apt-get install -y openjdk-17-jdk maven git && apt-get clean

  # 3. CleanKoda Code and Dependencies
  WORKDIR /app
  COPY ./agent-code /app
  RUN pip install --no-cache-dir -r requirements.txt

  # 4. The starting signal
  CMD ["python", "run_agent.py"]
```

## 4. The Stateless Lifecycle ("Fire and Forget") in the Serverless World

The agent never waits for a human. Waiting consumes processing time. The process is strictly asynchronous and stateless:

1. Job Creation: Flask starts the job and passes the task parameters (`TICKET_ID`, etc.).

2. Local Execution: LangGraph starts up, knows exactly what to do based on the variables, and clones the code to the local file system (`/workspace`).

3. The Self-Healing Loop: The agent modifies the code and tests it locally (e.g., `os.system("mvn test")`).

4. Completion & Scale-to-Zero: The agent pushes the pull request to GitHub and enters the status into the Supabase database. Python then reaches script termination (`sys.exit(0)`).

5. Hard Kill: In the millisecond that Python terminates, Google (or the local Docker daemon via `remove=True`) shuts down the container. The temporary code is deleted, and the cost drops to €0.00.

## 5. Advantages of the Approach

- Seamless B2B onboarding: Customers don't need to open firewalls for Jira. An OAuth login is all that's required.

- Unlimited scalability: 100 parallel tickets mean 100 isolated containers managed in parallel by Google.

- Maximum cost control: Thanks to the shift-left approach (Flask checks, agent works), not a single CPU second is wasted waiting for tasks.

## 6. Monetization & LLM Routing (Hybrid Billing)

The system is divided into two plans. The backend dynamically determines whose costs the agent will incur.

- **"Start Free" Plan (BYOK):** Users provide their own OpenAI/Anthropic API key. The user bears 100% of the LLM costs. Additionally, the repository size is limited to restrict cloud costs.

- **"Paid Plans" (Bundled SaaS):** CleanKoda uses its master API key; LLM and cloud costs are cross-subsidized by the SaaS fee.

## 7. Database & Multi-tenancy (Supabase)
To guarantee a stateless architecture, Supabase (serverless PostgreSQL) completely replaces local databases.

**1. Auth & Identity:** Supabase manages the login system (JWT tokens) securely and scalably: Supabase handles the entire login system (e.g., "Sign in with GitHub" or "Sign in with Google"). Flask does not need to store passwords. We use Supabase's secure JWT tokens (JSON Web Tokens) to manage user sessions in the dashboard.

**2. Multi-tenancy (RLS):** Each table is assigned a tenant_id. Supabase's "Row Level Security" (RLS) ensures at the database level that a user may only read or edit rows where the tenant_id matches their own user ID. Even in the event of a bug in our Flask backend, Customer A can never see Customer B's data.

**3. Operations Dashboard:** The Supabase Studio web interface serves as a direct admin panel. CleanKoda does not require its own admin panel. The Supabase Studio (web interface) acts as a control center: Here you can immediately see new registrations, active agent jobs, connected repositories, and, in the case of support requests, directly view the logs (agent_logs table) of a specific job.

## 8. The Hybrid Strategy: Serverless & On-Premise from ONE Codebase

As shown in Chapter 2, we support two completely different deployment models from the exact same codebase using the DEPLOYMENT_MODE variable.

Architectural Comparison

| Property | SERVERLESS (SaaS / Cloud Run) | ON_PREMISE (Enterprise / On-Premise Server)
| ----------- | ------------------------------ | ----------------------------------------- |
| Trigger Logic | Flask starts a job via Google API | Flask starts a container via Docker API |
| Agent Lifecycle | 1 cycle -> Code push -> sys.exit(0) | Continuous loop (Waiting & Pulling) |
| Cost Impact | Scale-to-Zero (Costs only incurred during work) | Fixed costs (hardware runs 24/7 anyway) |

### The lifecycle switch (in the agent run_agent.py)

The base image (`Dockerfile`) is identical for both worlds. The magic happens in the agent's Python entry point, where, depending on the mode, it either dies after one run or remains permanently alive:

```python
import os
import sys
import time
from langgraph_agent import run_single_cycle

def main():
    mode = os.environ.get("DEPLOYMENT_MODE", "SERVERLESS")
    
    if mode == "SERVERLESS":
        # 1 Zyklus und sofortige Selbstzerstörung (GCP Scale-to-Zero)
        print("Starte im Serverless-Modus...")
        run_single_cycle()
        print("Zyklus beendet. Container terminiert sich.")
        sys.exit(0) 
        
    elif mode == "ON_PREMISE":
        # Dauerbetrieb: Der Container wartet auf dem Enterprise-Server
        print("Starte im On-Premise Dauerbetrieb...")
        while True:
            has_work = run_single_cycle()
            if not has_work:
                print("Warte auf neues Ticket...")
                time.sleep(60) # Schlafen bis zum nächsten Prüf-Zyklus

if __name__ == "__main__":
    main()
```

This clean abstraction makes CleanKoda a B2B product ready for use by both cost-conscious startups (SaaS in the Google Cloud) and highly regulated corporations (on-premise in banks) without any additional architectural effort!
