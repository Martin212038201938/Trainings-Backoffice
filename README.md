# Trainings-Backoffice

Eine modulare, API-orientierte Backoffice-Plattform für die Verwaltung mehrerer Trainingsmarken (NeWoa, Yellow-Boat, copilotenschule.de etc.).

## Features der aktuellen Version
- **FastAPI-Backend** inklusive SQLAlchemy-Datenmodell für Marken, Kunden, Trainer, Trainings, Aufgaben und Vorlagen.
- **Mandantenfähigkeit light**: Zuordnung von Kunden und Trainern zu beliebigen Marken.
- **Trainings-Workflow** mit Status, Checklisten-Tasks (Online vs. Classroom) und Aktivitätenprotokoll.
- **Schnell-Suche** über Kunden, Trainer und Trainings.
- **Seed-Daten** für Beispielkunden, Trainer, Marken sowie ein erstes Pilot-Training.
- **Platzhalter-KI-Funktionen** (E-Mail-Vorschläge, Notiz-Zusammenfassungen) zur einfachen Anbindung der OpenAI API.

## Projektstruktur
```
backend/
  app/
    config.py           # Environment-Handling
    database.py         # SQLAlchemy Engine & Session
    main.py             # FastAPI-Entry-Point
    models/             # Datenmodelle & Enums
    routers/            # REST-Endpoints (Brands, CRM, Trainings, Tasks, Suche)
    schemas/            # Pydantic-Schemas für Requests/Responses
    services/
      checklist.py      # Automatische Checklisten pro Trainingstyp
      ai.py             # Platzhalter für OpenAI-Anbindung
    seed_data.py        # Skript für Beispielinhalte
  pyproject.toml        # Poetry-Konfiguration
```

## Lokale Entwicklung
1. **Poetry installieren** (falls noch nicht vorhanden): https://python-poetry.org/docs/#installation
2. Abhängigkeiten installieren und virtuelle Umgebung aktivieren:
   ```bash
   cd backend
   poetry install
   poetry shell
   ```
3. Datenbank initialisieren + Seed-Daten laden:
   ```bash
   python -m app.seed_data
   ```
4. API starten:
   ```bash
   uvicorn app.main:app --reload
   ```
   Die API ist anschließend unter http://localhost:8000 und mit interaktiver Doku unter http://localhost:8000/docs erreichbar.

## Deployment-Hinweise (alwaysdata)
- Repository auf den alwaysdata-Server klonen.
- In der gewünschten Python-Version (>=3.11) Poetry installieren und wie oben beschrieben Dependencies installieren.
- `uvicorn` oder `gunicorn` als Daemon/Process definieren, z. B.:
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```
- Für tägliche Backups: Cronjob einrichten, der die SQLite-DB bzw. zukünftige PostgreSQL-Datenbank in den Backup-Speicher kopiert.
- SMTP-Daten pro Marke können später über Environment-Variablen in `app/config.py` hinterlegt werden.

## Nächste Ausbaustufen
- Benutzer- und Rollenmodell (Backoffice vs. Trainer) inkl. Authentifizierung.
- Frontend (z. B. Next.js oder React Admin) auf Basis der vorhandenen API.
- Erweiterte Automatisierungen: Reminder-E-Mails, Statusabhängigkeiten, Export-Funktionen.
- Lexoffice-Anbindung für Angebote/Rechnungen.
- Echte OpenAI-Integration in `services/ai.py` mit passenden Prompts und Kontextdaten.
