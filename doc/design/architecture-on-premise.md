# On-Premise Architektur von CleanKoda

Dieses Dokument beschreibt die On-Premise-Architektur für CleanKoda. Im Gegensatz zur event-gesteuerten Serverless-Architektur in der Cloud, bei der Agenten ("Worker") dynamisch pro Ticket als isolierte Jobs gestartet und wieder zerstört werden, basiert das On-Premise-Modell auf statischen, dauerhaft laufenden Docker-Containern. Dies eignet sich hervorragend für den Betrieb auf dedizierten Unternehmensservern (VMs), in internen Rechenzentren oder virtuellen privaten Clouds.

## 1. Übersicht der Systemkomponenten

In der On-Premise-Deployment-Variante werden zur Laufzeit primär **zwei getrennte Docker-Container** auf dem Zielserver (oder lokal zur Entwicklung) bereitgestellt:

### 1.1 Flask-App (Frontend / API Gateway)
Die Webanwendung läuft durchgehend in einem eigenen Container und stellt das User Dashboard sowie die Konfigurationsoberflächen (Target-Repositories, Task-Issue-Systeme und LLM-APIs) bereit. Sie dient als visuelle Steuerzentrale für den menschlichen Entwickler, um den Status des Agenten, die generierten Pläne und aktuellen Pull Requests zu überwachen.

### 1.2 Agent (Worker / Workbench)
Der autonome KI-Entwickler läuft in einem separaten Container. Da hier keine Serverless-Restriktionen oder Minutenabrechnungen greifen, operiert das System in einer **endlosen Hauptschleife** innerhalb der zentralen Methode (`run_agent.py`). Dieser "Fat Image"-Container enthält neben der LangGraph-Agentenlogik auch alle erforderlichen Werkzeuge der Workbench (z. B. Java, Maven, Git), um den Code zur Laufzeit lokal übersetzen und testen zu können.

## 2. Die Supabase-Datenanbindung

Die Anbindung an die zentrale Supabase-Datenbank **bleibt identisch** zur Serverless-Variante:
- Das **Frontend** kommuniziert über das Supabase SDK, verwaltet den Login durch die Nutzer (Authentifizierung) und speichert die Credentials für Mandanten.
- Der **Agent** greift ebenfalls sicher über die Supabase-Schicht zu, nutzt die in Supabase gekapselten Konfigurationen und schreibt beständig seine "Agent Actions" und Thought-Logs (Gedankenprotokolle) weg. 
Die bestehende Struktur der Tabellen und die generelle Logik bleiben vollständig erhalten.

## 3. Der autonome Worker-Loop (Kein Triggering via Frontend)

Der größte architektonische Unterschied zur Cloud-Job-Variante liegt im Trigger-Mechanismus zur Aufgabenaufnahme. In der Serverless-Architektur fungiert das Frontend aktiv als "Smart Poller", der den teuren Cloud-Job des Agenten erst gezielt über einen API-Aufruf anstößt, wenn im Issue-Tracker (Gibt es Arbeit?) eine neue Aufgabe erkannt wurde.

**Bei der On-Premise Installation entfällt dieser komplexe Trigger-Mechanismus:**
- Da der Agent-Container ohnehin dauerhaft läuft (z. B. via `restart: always` in Docker Compose), übernimmt er das Polling selbstständig.
- Die `run_agent.py` läuft in einer Endlosschleife und prüft in regelmäßigen Abständen direkt gegen die konfigurierten Task-Systeme (Trello/Jira), ob sich neue Tickets in der definierten "CleanKoda Backlog"-Spalte befinden.
- **Workflow:** Sobald das Issue-Tracking-System (über den Agenten selbst) meldet, dass Arbeit vorhanden ist, klont er den Code, arbeitet das Ticket ab, führt lokale Unit-Tests durch, postet ein Status-Update in die Queue und erstellt den Pull Request. Danach prüft das Loop-Script direkt das nächste Ticket – oder pausiert (Idle-Zeit/Sleep), sollte der Backlog leer sein.
- **Hauptvorteil:** Die Flask-App und insbesondere der Webbrowser des Kunden müssen **weder geöffnet noch per Hintergrund-Job (JS/Scheduler) getriggert** werden. Der Agent ist zu 100 % autark, solange der Container auf dem Server läuft.

## 4. Lokale Persistenz & Sicherheit

- Bei Cloud Run Jobs (Scale-to-Zero) werden temporär aufgesetzte Workspaces und Git-Clones beim Beenden des Jobs vernichtet. Beim On-Premise Deploying kann der Container dedizierte Mounts bzw. Host-Verzeichnisse als Docker-Volumes (z. B. `-v /host/workspace:/workspace`) nutzen. Dies beschleunigt Folge-Tasks enorm, da Build-Caches erhalten bleiben oder Repositories nicht komplett neu initialisiert werden müssen (Incremental Builds).
- Durch den Betrieb innerhalb des abgesicherten Firmennetzwerks (hinter Firewalls) garantiert das System hohe Code-Souveränität, wobei Projektzusammenfassungen und das Status-Dashboard über das identische Supabase-Frontend abgerufen werden können.

## 5. Deployment Beispiel (Docker Compose)

Das On-Premise Setup lässt sich äußerst simpel über eine `.env`-gesteuerte `docker-compose.yaml` realisieren:

```yaml
version: '3.8'

services:
  cleankoda-frontend:
    build: 
      context: .
      dockerfile: Dockerfile.cleankoda-frontend
    ports:
      - "5000:5000"
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}

  cleankoda-agent:
    build:
      context: .
      dockerfile: Dockerfile.cleankoda-agent
    volumes:
      - ./workspace:/workspace 
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
    restart: unless-stopped
```
