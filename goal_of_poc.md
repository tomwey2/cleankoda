# Ziel des POCs

## Vision: Solve the Talent Bottleneck with Artificial Developers
Vision ausarbeiten

## LLM Integration
Anpassung der Funktion get_llm() im Modul llm_factory.py
- Integration der KI Provider OpenRouter und Ollama 
- Umstieg auf die Factory-Funktion `init_chat_model()` für alle LLM Provider

## Qualität des Coding Agenten
- robust (z.B. wenn zuviele Tokens erzeugt werden), LLM Aufruf verfeinern (welche Messages braucht man)
- gute Architektur
- Ergebnis des Coding Agent darf kein Schrott sein (im PR)
  - braucht man bestimmte Modelle?
  - Qualitätssicherung durch Tests 
  - Sauberer Code
  - gute Systemprompts

## Show Case
- existierendes Open Source forken und ein Feature hinzufügen
- task-tracker repo Feature OAuth2

## Prozess
### Human in the Loop Prozess innerhalb von Trello
Vorübergehender Prozess, solange die Anbindung zum GitHub PR nicht vorhanden ist:
Wenn der PR nicht akzeptiert wird, soll der Benutzer den Task auf "In Progress" zurück gesetzen können. Dabei wird der Kommentar des PR als Comment in die Trello Card eingefügt.
Der Agent soll dann den Task in "In Progress" wieder aufnehmen und den Code neu generieren. Diesmal unter Berücksichtigung des PR Kommentars.

Teil dieser Funktion ist es, das der Agent priorisiert seine Aufgaben aus der Liste "In Progress" entnehmen soll. Nur wenn dort keine Aufgaben vorhanden sind, soll er die nächste Aufgabe aus der Liste "Sprint Backlog" entnehmen (wie gehabt).

### Loop innerhalb von GitHub PR umsetzen (evtl. nicht im POC)
### Create a new Trello Card after Analyse Task
Wenn der Agent eine Analyse (ohne Codegenerierung) durchführen soll, sollen folgende Ergebisse je nach Art der Analyse produziert werden:
1. **Aktuelle Umsetzung** Wenn die Analyse ein Frage zur Codebase ist (z.B. "Wieviele Unit Tests gibt es?"), dann soll soll das Ergebnis der Analyse als Kommentar in die Karte geschrieben werden und die Karte auf "In Review" gestellt werden.
2. **neue Umsetzung** Wenn die Analyse eine Aufforderung zur Planerstellung für ein neues Feature oder für ein Bugfix ist, dann soll der Agent das Ergebnis der Analyse in eine neue Karte auf Trello in die Liste "Backlog" einfügen. Der Agent kommertiert dies in der Analyse Karte stellt diese auf "In Review".


├── app
│   ├── agent
│   │   ├── nodes
│   │   ├── graph.py
│   │   ├── worker.py
│   │   ├── ...
│   ├── templates
│   │   ├── index.html
│   ├── main.py
│   ├── models.py <-- AgentConfig
│   ├── webapp.py <-- Flask
│   ├── ...
