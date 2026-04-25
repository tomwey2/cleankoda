# Software Architektur

Dieses Dokument bietet einen strategischen High-Level-Überblick über die Architektur von CleanKoda. Detaillierte technische Spezifikationen zu spezifischen Unterthemen oder Deployment-Strategien wurden in dedizierte Dokumente ausgelagert, die hier entsprechend verlinkt sind.

## 1. Einleitung & Systemüberblick

CleanKoda ist ein KI-gestütztes Tool, das Software-Tickets (Issues) autonom analysiert, Code-Anpassungen vornimmt und diese als Pull-Requests in Repositories (z. B. GitHub, Bitbucket) zur Verfügung stellt. 
Die Architektur basiert auf der strikten Trennung zwei logischer Kernkomponenten:
- **Das User Frontend & Steuerungs-Backend (Flask):** Zuständig für das Web-Dashboard, die Verwaltung von Zugangsdaten, Billing, und die Orchestrierung der Agenten-Jobs.
- **Die isolierte Agenten-Engine:** Die eigentliche „Arbeiter-Umgebung“, in welcher der Code geklont wird und die LLMs (z. B. Mistral, Gemini, Anthropic) iterativ über LangGraph/LangChain an der Lösung arbeiten.

## 2. High-Level Komponenten-Diagramm

Das folgende Diagramm veranschaulicht die übergeordnete Architektur des Systems:

![Architecture](../images/cleankoda-architecture.png)

Das System interagiert mit verschiedenen **externen Diensten**, um den gesamten Workflow abzudecken:

- **Issue Tracking System (z. B. Trello):** Dient als zentrale Informationsquelle für eingehende Programmieraufgaben. Der Agent ruft Aufgaben aus dem Backlog ab und aktualisiert deren Status nach Abschluss.
- **LLM-Anbieter (z. B. Mistral, OpenAI):** Die Inferenz-Engine, die vom Agenten zur Codegenerierung, Fehleranalyse und Anforderungsanalyse verwendet wird.
- **Kollaborative Versionskontrolle (z. B. GitHub):** Das Ziel für den generierten Code. Der Agent überträgt Änderungen automatisch und erstellt Pull Requests zur Überprüfung durch Entwickler.

## 3. Deployment Modelle (Die Hybride Strategie)

Die Architektur ist so konzipiert, dass **exakt dieselbe Codebasis** zerschnitten und in völlig unterschiedlichen Umgebungen betrieben werden kann. Dies ermöglicht sowohl einen effizienten SaaS-Betrieb als auch eine Unternehmensintegration.

- **SaaS / Serverless Cloud:** Der Agent lebt nur für die Dauer eines Jobs. Maximale Kosteneffizienz durch "Scale-to-Zero".
  👉 *Details siehe: [`architecture-serverless.md`](./architecture-serverless.md)*
- **Enterprise / On-Premise Server:** Agent und App laufen als langlebige Container ("Long-Running") auf unternehmenseigener Hardware.
  👉 *Details siehe: [`architecture-on-premise.md`](./architecture-on-premise.md)*

👉 Details siehe: [`deployment.md`](./deployment.md)

## 4. Datenbank, Auth & Multi-Tenancy

CleanKoda setzt strikt auf eine zustandslose App-Architektur (Stateless). Jeglicher State, Sessions und Authentifizierungsprozesse werden über **Supabase** (Serverless PostgreSQL) abgewickelt. Dank Row Level Security (RLS) wird auf Datenbankebene sichergestellt, dass Daten zwischen Kundenkonten (Mandanten) strikt isoliert bleiben.

👉 *Details siehe: [`database.md`](./database.md)*

## 5. Guardrails & Ressourcenschutz

KI-Agenten können unvorhersehbar agieren oder in Schleifen geraten. Die Software-Architektur wird daher durch harte Sicherheitsleitplanken (Guardrails) auf Backend-Ebene geschützt. Diese Guardrails regeln die Laufzeiten, Repository-Größen und LLM-Kontingente dynamisch anhand der gebuchten Pläne.

👉 *Details siehe: [`guardrails.md`](../business/guardrails.md) & [`pricing.md`](../business/pricing.md)*


## 6. Die Hybridstrategie: Serverless & On-Premise mit nur einer Codebasis

Wie in Kapitel 3 gezeigt, unterstützen wir zwei völlig unterschiedliche Deployment Modelle mit ein und derselben Codebasis mithilfe der Umgebungsvariable `DEPLOYMENT_MODE`.

Architekturvergleich

| Eigenschaft | SERVERLESS (SaaS / Cloud Run) | ON_PREMISE (Enterprise / On-Premise Server)
| ----------- | ------------------------------ | ----------------------------------------- |
| Trigger Logik | Flask startet einen Job über die Google API | kein Trigger notwendig |
| Agent Lifecycle | 1 Zyklus -> Code-Push -> sys.exit(0) | Endlosschleife (Warten & Ziehen) |
| Cost Impact | Scale-to-Zero (Kosten fallen nur während der Arbeit an) | Fixkosten (Hardware läuft sowieso 24/7) |

## 7. Der Lifecycle-Switch (in der Agenten-Laufzeit `run_agent.py`)

Das Basis-Images (`Dockerfile`) sind in beiden Umgebungen identisch. Die eigentliche Magie geschieht im Python-Einstiegspunkt des Agenten, wo er je nach Modus entweder nach einem Durchlauf beendet wird oder dauerhaft aktiv bleibt:

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

Durch diese klare Abstraktion ist CleanKoda ein B2B-Produkt, das sowohl von kostenbewussten Startups (SaaS in der Google Cloud) als auch von stark regulierten Unternehmen (On-Premise in Banken) ohne zusätzlichen architektonischen Aufwand eingesetzt werden kann!
