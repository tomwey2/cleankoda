# Serverless-Architektur von CleanKoda auf Google Cloud Run

Dieses Dokument beschreibt die skalierbare Serverless-Architektur für CleanKoda auf der Google Cloud Platform (GCP). Diese Architektur adressiert spezifische Cloud-Herausforderungen (wie das Fehlen gemeinsamer Speicher in der Cloud), ermöglicht ein nahtloses Kunden-Onboarding und optimiert die Betriebskosten durch intelligentes Event-Routing ("Scale-to-Zero"). Die Architektur ergänzt die im README beschriebene Vision eines autonomen, containerisierten KI-Softwareentwicklers.

## 1. Übersicht der verwendeten GCP-Produkte

Obwohl CleanKoda vollständig serverless betrieben wird, kommen zwei unterschiedliche Cloud Run-Bereitstellungsmodelle für das Frontend (Dashboard/Gateway) und den Agenten (Worker mit Workbench) zum Einsatz:

### 1.1 Flask-App (Frontend/Gateway) als *Google Cloud Run Service*
- **Warum dieses Modell?** Ein Cloud Run Service ist darauf ausgelegt, auf eingehenden HTTPS-Traffic zu reagieren. Er erwacht in Millisekunden, liefert das Dashboard aus, nimmt Webhooks entgegen und skaliert automatisch bei hohem Nutzeraufkommen. Da CleanKoda als sicheres und reaktionsschnelles Portal dient, ist dies die optimale Wahl.

### 1.2 Agent (Worker/Fat Image) als *Google Cloud Run Job*
- **Warum dieses Modell?** Ein Job wartet nicht auf kontinuierlichen Web-Traffic, sondern ist prädestiniert für asynchrone, rechenintensive KI-Aufgaben. Der LangGraph-basierte Agent kann über längere Zeiträume völlig autonom arbeiten ("Fire-and-Forget") und beendet sich selbstständig, sobald der Code analysiert, geschrieben und der Pull Request erstellt wurde.

## 2. Intelligentes API-Gateway & Event-Trigger (Shift-Left)

Um zu verhindern, dass der ressourcenintensive KI-Agent "leer" anläuft und unnötige Kosten verursacht, fungiert die zustandslose Flask-App als intelligenter Gatekeeper. Die Prüflogik ("Gibt es Arbeit?") wird in das kostengünstige Frontend verlagert (Shift-Left). Der Cloud Run Job des Workers wird erst gestartet, wenn tatsächlich neue Aufgaben aus dem Issue-Tracking-System (z. B. Trello, Jira) vorliegen.

### 2.1 Trigger: Smart Polling des Issue-Trackers
Das System prüft regelmäßig, ob der Agent Aufgaben bearbeiten soll. Wie im README dargelegt, fügt sich der Agent nahtlos in bestehende Systeme ein:

1. Der menschliche Benutzer loggt sich ein und sieht sein Dashboard.
2. Das Flask-Backend fragt blitzschnell das verknüpfte Issue-Tracking-System ab.
3. Gibt es keine neuen Tickets in der für CleanKoda definierten Spalte, liefert Flask lediglich ein `200 OK`. Es wird kein Worker gestartet, wodurch die Kosten bei exakt €0,00 bleiben.
4. Ändert sich der Status eines Tickets (oder wird in GitHub ein Pull-Request-Kommentar hinzugefügt), wird das Ereignis dem Mandanten (Tenant) zugeordnet und gezielt ein Worker-Job gestartet.

#### Variante A: Frontend-Polling via Browser
- Ein unsichtbares JavaScript-Intervall im aktiven Browserfenster des Nutzers sendet periodisch (z. B. alle 5 Minuten) eine unauffällige AJAX-Anfrage an das Flask-Backend (`/api/sync-tasks`).
- Da der Aufruf aus der Browser-Session des berechtigten Nutzers erfolgt, wird das JWT/Supabase-Token automatisch und sicher mitgeliefert.
- **Vorteile:** Keine zusätzliche Infrastruktur (wie Cloud Scheduler oder Service Accounts) erforderlich. Die Row Level Security (RLS) in der Datenbank greift perfekt.
- **Nachteil:** Der Abgleich stoppt, sobald der Browser-Tab geschlossen oder das Smartphone gesperrt wird.

**Beispiel-Implementierung im Frontend (`dashboard.html` / `base.html`):**
```html
<script>
    const SYNC_INTERVAL_MS = 5 * 60 * 1000; // 5 Minuten
    
    function checkTasksInBackground() {
        fetch('/api/sync-tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(response => {
            if (response.ok) {
                console.log("Automatischer Background-Sync erfolgreich angestoßen.");
            }
        })
        .catch(error => console.error("Sync fehlgeschlagen:", error));
    }

    document.addEventListener('DOMContentLoaded', () => {
        setInterval(checkTasksInBackground, SYNC_INTERVAL_MS);
    });
</script>
```

#### Variante B: Google Cloud Scheduler (via Serverless Cron)
Zusätzlich kann ein serverless Cronjob über den Google Cloud Scheduler konfiguriert werden, der das Backend zeitgesteuert abfragt. Dies lässt sich auf die Arbeitszeiten des Kunden begrenzen (z. B. Mo-Fr, 08:00 - 18:00 Uhr via `*/5 8-18 * * 1-5`), um Ressourcen zu sparen und trotzdem im Hintergrund autark arbeiten zu können.

## 3. Technische Umsetzung im Backend (Hybrid-Strategie)

Wie im README beschrieben, ist CleanKoda für den Betrieb "on premise", lokal und in der Cloud entwickelt worden. Die Flask-App steuert dies über die Umgebungsvariable `DEPLOYMENT_MODE`. Je nach Umgebung wird der Agent lokal (als Docker-Container über die Docker-API) oder in der Cloud (als GCP Cloud Run Job) instanziiert.

### Schritt 1: Flask ruft den Agenten auf und reicht den Supabase Token weiter

Dabei wird dem Worker das aktuelle JWT (access_token) der Supabase-Benutzersession als Umgebungsvariable mitgegeben. Da der Token meist nur eine Stunde gültig ist, erbt der Worker just-in-time die strikten Datenzugriffsrechte des Users (Zero-Trust-Ansatz). Die Supabase Row Level Security (RLS) greift infolgedessen zu 100 %.

**Hybrid-Router in Python (Auszug):**
```python
import os
import docker
from google.cloud import run_v2

def spawn_agent_worker(project_id, region, target_language, ticket_id, repo_url, tenant_id, pr_feedback=None):
    mode = os.environ.get("DEPLOYMENT_MODE", "SERVERLESS")
    
    env_vars = {
        "TICKET_ID": ticket_id,
        "REPO_URL": repo_url,
        "TENANT_ID": tenant_id,
        "DEPLOYMENT_MODE": mode
    }
    if pr_feedback:
        env_vars["PR_FEEDBACK"] = pr_feedback

    if mode == "SERVERLESS":
        return _spawn_gcp_cloud_run_job(project_id, region, target_language, env_vars)
    elif mode == "ON_PREMISE":
        return _spawn_local_docker_container(target_language, env_vars)
    else:
        raise ValueError(f"Unbekannter DEPLOYMENT_MODE: {mode}")

def _spawn_gcp_cloud_run_job(project_id, region, target_language, env_vars):
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


## 4. Der Worker: Das "Fat Image" Pattern

Im Einklang mit der im README beschriebenen Architektur wird der autonome Agent strickt von der Ausführungsumgebung (Workbench) getrennt betrachtet, aber aus Infrastruktur-Gründen im selben Image gebündelt. Da bei Cloud Run Jobs keine übergreifenden Netzwerkfestplatten gemountet werden, nutzen wir das **Fat Image Pattern**. Beide Komponenten werden für das LangGraph-Framework passend in einem einzigen Docker-Image verpackt. So stellen wir sicher, dass "Integrated Build Management & QA" lokal funktioniert, bevor der Code gepusht wird.

Beispielsweise wird für Java-Entwicklungsumgebungen ein spezifisches Base-Image erstellt.

**Beispiel `Dockerfile.java`:**
```dockerfile
# 1. Das offizielle Python Basis-Image
FROM python:3.11-slim

# 2. Die Workbench: Java 17, Maven und Git installieren
RUN apt-get update && apt-get install -y openjdk-17-jdk maven git && apt-get clean

# 3. Den CleanKoda-Code und Abhängigkeiten kopieren
WORKDIR /app
COPY ./agent-code /app
RUN pip install --no-cache-dir -r requirements.txt

# 4. Das Startkommando
CMD ["python", "run_agent.py"]
```

## 5. Zustandsloser Lebenszyklus ("Fire and Forget")

Der autonome Tool-Stack (Analyst, Coder, Tester) darf aus Kosten- und Performancegründen niemals passiv warten. Der Prozess ist daher vollständig zustandslos und asynchron entworfen:

1. **Job Start:** Flask startet den Job parallel und übergibt die benötigten Variablen (`TICKET_ID`, etc.).
2. **Lokale Reproduktion:** LangGraph fährt hoch, ruft den Kontext ab, nutzt das Model Context Protocol (MCP) für Git-Operationen und klont den Workspace (`/workspace`).
3. **Die Selbstheilende Schleife (Healing Loop):** Der Code wird angepasst und fortlaufend in der lokalen Workbench (z. B. `mvn test`) getestet, wie es die "Trust-First"-Strategie von CleanKoda verlangt.
4. **Erfolgreicher Abschluss:** Nach erfolgreichem Test wird mittels "Explainable PR"-Logik eine verständliche Pull Request zusammengefasst. Anschließend terminiert sich das Skript ordnungsgemäß (`sys.exit(0)`).
5. **Hard Kill:** In der gleichen Millisekunde veranlasst Google Cloud Run (bzw. Docker mit `--rm`) das Herunterfahren des Containers. Temporäre Arbeitsdaten werden verworfen und die verbrauchte Rechnerleistung skaliert sofort auf Null.

## 6. Zusammenfassende Vorteile dieses Ansatzes

- **Nahtloses Enterprise-Onboarding:** Kundenunternehmen müssen für das Agent-System keine internen Jira- oder Trello-Instanzen ans Internet freigeben. Eine ausgehende Token-basierte oder OAuth-Anbindung reicht aus.
- **Grenzenlose Skalierbarkeit:** Eine Arbeitslast von 100 anstehenden Tickets führt lediglich dazu, dass zeitgleich 100 parallel ablaufende und voneinander isolierte Container innerhalb von Google hochgefahren werden.
- **Totale Kostenkontrolle ("Scale to Zero"):** Dank des "Shift-Left"-Mechanismus werden Serverressourcen ausschließlich dann verrechnet, wenn der KI-Mitarbeiter auch real an zugewiesenen Aufgaben arbeitet.
