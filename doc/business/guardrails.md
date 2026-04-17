## Business Guardrails & Limits

CleanKoda bietet als SaaS-Plattform verschiedene Preispläne an: **FREE, PRO, TEAM und ENTERPRISE**. 
Um einen wirtschaftlichen Betrieb zu gewährleisten und Missbrauch (z. B. durch gigantische Repositories oder endlose LLM-Schleifen) zu verhindern, greifen sogenannte **Guardrails** (Leitplanken).

### Übersicht der Limitierungen (The Guardrails)

Guardrails schützen sowohl die Infrastruktur als auch das Start-up Budget. Folgende Metriken bieten sich für die Differenzierung der Pläne an:

1. **Repository-Größe (`max_repo_mb`)**
   - *Problem:* Große Repositories blähen den Vektor-Speicher auf und treiben die Token- und Compute-Kosten für die Code-Analyse in die Höhe.
   - *Lösung:* FREE = 50 MB, PRO = 500 MB, ENTERPRISE = unbegrenzt.
2. **Monatliche Agenten-Läufe (`max_agent_runs_per_month`)**
   - *Problem:* Jeder Agenten-Lauf generiert unmittelbare Kosten bei OpenAI, Anthropic oder anderen LLM-Providern.
   - *Lösung:* FREE = 10 Jobs/Monat, PRO = 100 Jobs/Monat.
3. **Ausführungszeit pro Job (`max_execution_minutes`)**
   - *Problem:* Agenten könnten in Logik-Endlosschleifen geraten und Compute-Ressourcen auf den Serverless-Workern binden.
   - *Lösung:* Der Laufzeit-Container für einen FREE-Plan wird nach 15 Minuten hart abgebrochen. PRO-Jobs dürfen 60 Minuten laufen.
4. **Verfügbare LLM-Modelle (`allowed_llm_models`)**
   - *Problem:* State-of-the-Art Modelle sind um ein Vielfaches teurer als kleinere Einstiegsmodelle.
   - *Lösung:* Der FREE-Plan erlaubt nur effiziente Modelle (z. B. Gemini 1.5 Flash, GPT-3.5). Der PRO-Plan schaltet Premium-Modelle frei (GPT-4o, Claude 3.5 Sonnet).
5. **Gleichzeitige Jobs (`max_concurrent_jobs`)**
   - *Lösung:* Im FREE-Plan wird nur ein 1 Ticket gleichzeitig pro Nutzer abgearbeitet. Weitere rutschen in eine Warteschlange. ENTERPRISE ermöglicht die parallele Abarbeitung mehrerer Tickets.

### Architektur: Das Single Responsibility Principle (SRP)

Die zentrale Anlaufstelle für die Durchsetzung dieser Regeln ist der **Guardrail Service** (`guardrails_service.py`). Dieser kapselt die gesamte Geschäftslogik bezüglich der SaaS-Limits, anstatt sie quer über verschiedene Routen und Module der Applikation zu verstreuen.

```python
import requests
from urllib.parse import urlparse

class GuardrailException(Exception):
    """Eigene Exception, wenn ein SaaS-Limit überschritten wird."""
    pass

class GuardrailService:
    # Zentrale Definition der globalen SaaS-Limits
    LIMITS = {
        'FREE': {
            'max_repo_mb': 50.0,
            'max_agent_runs': 10,
            'allowed_models': ['gemini-1.5-flash', 'gpt-3.5-turbo']
        },
        'PRO': {
            'max_repo_mb': 500.0,
            'max_agent_runs': 100,
            'allowed_models': ['gemini-1.5-pro', 'gpt-4o', 'gemini-1.5-flash']
        },
        'ENTERPRISE': {
            'max_repo_mb': float('inf'),
            'max_agent_runs': float('inf'),
            'allowed_models': ['ALL']
        }
    }

    @classmethod
    def validate_github_repo_size(cls, repo_url, user_plan='FREE', github_token=None):
        """
        Prüft vor der Speicherung, ob das Repository für den gewählten Plan zulässig ist.
        """
        path_parts = urlparse(repo_url).path.strip('/').split('/')
        if len(path_parts) < 2:
            raise ValueError("Ungültige GitHub URL")
        
        owner, repo = path_parts[0], path_parts[1]
        
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {"Accept": "application/vnd.github.v3+json"}
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
            
        response = requests.get(api_url, headers=headers)
        
        if response.status_code != 200:
            raise ValueError(f"Repo konnte nicht gefunden werden (Status {response.status_code})")
            
        size_mb = response.json().get("size", 0) / 1024
        max_allowed = cls.LIMITS.get(user_plan, cls.LIMITS['FREE'])['max_repo_mb']
        
        if size_mb > max_allowed:
            raise GuardrailException(
                f"Dein Repository ist {size_mb:.1f} MB groß. "
                f"Der {user_plan}-Plan erlaubt maximal {max_allowed} MB. "
                "Bitte aktualisiere deinen Account."
            )
        
        return True

    @classmethod
    def validate_llm_model_access(cls, requested_model, user_plan='FREE'):
        """Prüft, ob der Nutzer das ausgewählte KI-Modell im aktuellen Plan verwenden darf."""
        allowed = cls.LIMITS.get(user_plan, cls.LIMITS['FREE'])['allowed_models']
        if 'ALL' not in allowed and requested_model not in allowed:
            raise GuardrailException(f"Das Modell {requested_model} ist im {user_plan}-Plan nicht verfügbar.")
        return True
```

### Die Zwei-Stufen-Validierung

Ein hervorragendes Nutzererlebnis gepaart mit absoluter Sicherheit wird durch das Zwei-Stufen-Prinzip erreicht:

**1. Die UX-Lösung (Frontend-Feedback)**
Im Flask-Frontend (z. B. bei der Repository-Konfiguration) wird Vanilla-JS oder htmx genutzt, um direktes Feedback zu geben. Sobald der User die URL seines Repos eingibt (z. B. beim `onblur`-Event), wird ein asynchroner API-Check an das eigene Backend ausgelöst.
- *Vorteil:* Der User bekommt sofort die Rückmeldung ("Dieses Repo ist zu groß für den Free Plan"), noch bevor er das Formular final absendet. Das vermeidet Frustration oder unverständliche Fehlermeldungen im Nachgang.

**2. Die Sicherheits-Lösung (Backend-Enforcement)**
Dies ist das eigentliche Sicherheitsnetz. Da Frontend-Checks trivial zu umgehen sind (z. B. über cURL), **muss** die Prüfung zwingend unmittelbar im Backend kurz vor der Ausführung erfolgen.
- *Logik:* Unmittelbar bevor in der Datenbank `db.session.add(setting)` oder beim Agenten `start_agent_job()` aufgerufen wird, verifiziert der Controller die Limits über den `GuardrailService`.
- *Integration:* Schlägt die Prüfung fehl, wird die `GuardrailException` abgefangen und dem Nutzer systematisch auf der Oberfläche präsentiert (z. B. über eine Flask `flash`-Message: *"Entschuldigung, Repos über 50MB erfordern einen PRO-Account. [Jetzt upgraden]"*). Dadurch entsteht nicht nur Sicherheit, sondern ein eingebauter Sales-Funnel.
