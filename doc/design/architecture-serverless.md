## CleanKoda's Serverless Architecture on Google Cloud Run
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

### Trigger: Smart Polling the Issue and starting the worker
We ask the Issue Tracking System periodically if there is a issue the agent should work on. 

1. The user logs in and sees their dashboard.
2. Flask makes a tiny, lightning-fast API call to the ticketing system (Jira/Trello). If there are no new tickets in the CleanKoda column, Flask responds with 200 OK. The resource-intensive worker job is not triggered (cost: €0).
3. If the ticket's status changes, Flask assigns the event to the tenant and immediately fires a targeted worker job that starts the agent.

The same applies to GitHub: If the status of a pull request changes (e.g., if a human developer adds a comment to the pull request, such as "Please make the button red"), the agent is called.

There are 2 variants:

#### 1. via Frontend Polling: 
- An invisible JavaScript interval starts (e.g., every 5 minutes).
- The script makes an unobtrusive API call (AJAX/Fetch) to your Flask app (e.g., /api/trigger-sync).
- Since this call originates from the logged-in user's browser, the standard Supabase session cookie / JWT token is automatically included!
- Advantages: No infrastructure overhead: no cloud scheduler, service accounts, OIDC, or JWT signing is required. Everything runs through the user's normal session. RLS works perfectly.
- The drawback: if the user closes the browser tab or their phone screen turns off, the automation stops immediately. The agent only cleans up the tickets again when the user opens CleanKoda next.

##### 1. The frontend (in your dashboard.html or base.html):

Insert this small script at the very bottom, before the closing </body> tag.
```html
<script>
    // Führt die Funktion alle 5 Minuten (300.000 Millisekunden) aus
    const SYNC_INTERVAL_MS = 5 * 60 * 1000; 

    function checkTasksInBackground() {
        // Ein unsichtbarer Call an dein Flask Backend
        fetch('/api/sync-tasks', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (response.ok) {
                console.log("Automatischer Background-Sync erfolgreich angestoßen.");
            }
        })
        .catch(error => console.error("Sync fehlgeschlagen:", error));
    }

    // Startet den Timer, sobald die Seite geladen ist
    document.addEventListener('DOMContentLoaded', (event) => {
        setInterval(checkTasksInBackground, SYNC_INTERVAL_MS);
        // Optional: Direkt beim ersten Laden einmal ausführen
        // setTimeout(checkTasksInBackground, 2000); 
    });
</script>
```

##### 2. The backend (in your Flask routes.py):

This is now super simple because we bypass all the security drama.

```python
from flask import jsonify, session

@app.route('/api/sync-tasks', methods=['POST'])
def sync_tasks_api():
    # 1. Ist der User eingeloggt?
    user_jwt = session.get("supabase_access_token")
    if not user_jwt:
        return jsonify({"error": "Unauthorized"}), 401

    # 2. Supabase Client GANZ NORMAL (mit RLS) initialisieren
    options = ClientOptions(headers={"Authorization": f"Bearer {user_jwt}"})
    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=options)
    
    # 3. Nachschauen, ob es ein aktives Task-System für diesen User gibt
    # RLS blockt automatisch alles Fremde ab!
    response = supabase.table("task_system").select("id").execute()
    
    if response.data:
        for system in response.data:
            # 4. Den Worker starten und ihm den normalen JWT übergeben
            trigger_agent_job(system['id'], user_jwt)
            
    return jsonify({"status": "Sync triggered"}), 200
```


#### 2. via Google Cloud Scheduler
- Google Cloud Scheduler (a serverless cron job) periodically calls a protected route in the Flask app.
- Smart Scheduling: To avoid unnecessary API calls at night or on weekends, the scheduler runs according to the customer's defined working hours (e.g., Mon-Fri, 8:00 AM - 6:00 PM via cron syntax */5 8-18 * * 1-5).


### Technical Implementation in Code (Flask Backend - Hybrid Setup)
Flask spawns the worker as soon as actual work has been validated. This is where our hybrid strategy comes into play: The gateway dynamically decides, via an environment variable (DEPLOYMENT_MODE), whether the agent is started via the Google API (SaaS) or via the local Docker environment (on-premises).

#### Schritt 1: Flask ruft den Agenten auf und reicht den Supabase Token weiter
In deiner Flask-App (wo der User ja bereits über Supabase eingeloggt ist), hast du Zugriff auf seinen aktuellen access_token (JWT). Diesen Token übergibst du als Umgebungsvariable (Override) an den Cloud Run Job.
Da der JWT nur maximal 1 Stunden gültig ist, treffen wir die Annahme, dass der Worker nicht länger für seine Arbeit braucht. Damit erbt der Worker exakt die Rechte des Users, und die Supabase Row Level Security (RLS) greift zu 100 %. Es wird kein Root-Key benötigt ("Zero Trust" Ansatz).

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
    # Retrieve the current JWT of the logged-in user
    user_access_token = session.get("supabase_access_token")

    client = run_v2.JobsClient()
    job_name = f"cleankoda-agent-{target_language}"
    job_path = client.job_path(project_id, region, job_name)

    request = run_v2.RunJobRequest(
        name=job_name,
        overrides={
            "container_overrides": [
                {
                    "env": [
                        # We are handing over the token
                        {"name": "USER_JWT", "value": user_access_token},
                    ]
                }
            ]
        }
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

#### Schritt 2: Der Worker nutzt den Token (Supabase Python SDK)
Im Python-Code des Cloud Run Jobs nutzen wir ganz normal den öffentlichen ANON_KEY. Über die ClientOptions sagen wir dem Client: "Hey, nutze für alle Anfragen diesen JWT-Token statt des Standard-Anon-Tokens!"

```
import os
from supabase import create_client, ClientOptions

# 1. Variablen auslesen
supabase_url = os.environ.get("SUPABASE_URL")
supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY") # Nur der öffentliche Key!
user_jwt = os.environ.get("USER_JWT")
task_system_id = os.environ.get("TASK_SYSTEM_ID")

# 2. Den Client mit dem User-Token initialisieren
# Wir überschreiben den Authorization-Header mit dem Token des Users
options = ClientOptions(headers={"Authorization": f"Bearer {user_jwt}"})
supabase = create_client(supabase_url, supabase_anon_key, options=options)

def run_agent():
    # 3. Datenbank-Abfrage
    # Da RLS jetzt aktiv ist, MÜSSEN wir nicht mal zwingend nach user_id filtern!
    # Supabase gibt uns sowieso nur die Zeilen, die diesem User gehören.
    response = supabase.table("task_system") \
        .select("*, tenant_credentials(*)") \
        .eq("id", task_system_id) \
        .execute()
        
    if not response.data:
        raise Exception("Zugriff verweigert oder Task nicht gefunden (RLS hat geblockt!)")
        
    task_data = response.data[0]
    print(f"Agent startet für System: {task_data['container_identifier']}")
    # ... Agenten Logik ...
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

