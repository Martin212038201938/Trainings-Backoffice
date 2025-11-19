# Projektstand Trainings-Backoffice
**Stand:** 19. November 2025
**Version:** 0.1.0 (MVP/Proof of Concept)

---

## Executive Summary

Das Trainings-Backoffice ist eine modulare API-Plattform für die Verwaltung mehrerer Trainingsmarken (NeWoa, Yellow-Boat, copilotenschule.de). Das Backend ist **funktional implementiert** und bietet alle Kern-Features für das Trainingsmanagement. Das System ist **lokal lauffähig**, aber noch **nicht produktionsbereit**.

**Status:** 🟡 **Development** - Backend MVP komplett, Frontend fehlt, Deployment-Vorbereitung erforderlich

---

## Was ist implementiert (✅ Fertig)

### Backend (FastAPI)
- ✅ **Datenmodell** - Vollständiges SQLAlchemy-Schema für:
  - Marken (Brands) mit individuellen Einstellungen
  - Kunden (Customers) mit Mandantenfähigkeit
  - Trainer mit regionalen Profilen
  - Trainings mit umfangreichem Workflow
  - Trainings-Katalog (Templates)
  - Tasks/Checklisten-System
  - Activity Logs für Audit-Trail
  - E-Mail-Templates

- ✅ **REST-API** - Vollständige CRUD-Endpoints für:
  - `/brands` - Markenverwaltung
  - `/customers` - Kundenverwaltung
  - `/trainers` - Trainerverwaltung
  - `/catalog` - Trainingskatalog
  - `/trainings` - Trainingsverwaltung mit Status-Workflow
  - `/tasks` - Task-Management
  - `/search` - Übergreifende Suche

- ✅ **Business Logic**
  - Automatische Checklisten-Generierung je Trainingstyp (Online vs. Classroom)
  - Status-Workflow für Trainings (Lead → Delivered → Invoiced)
  - Aktivitätenprotokollierung
  - Marken-Kunde-Trainer-Zuordnung (M:N)

- ✅ **Development Setup**
  - Poetry Dependency Management
  - SQLite-Datenbank (Development)
  - Seed-Daten für schnelles Onboarding
  - API-Dokumentation unter `/docs` (Swagger UI)

---

## Was fehlt (❌ Noch zu tun)

### Kritisch für Go-Live

1. **Frontend fehlt komplett** ❌
   - Kein UI für Endbenutzer
   - Nur API-Zugriff über `/docs` möglich
   - Empfehlung: React Admin, Next.js oder Vue.js

2. **Authentifizierung & Autorisierung** ❌
   - Keine Benutzerverwaltung
   - Keine Login/Session-Handling
   - Keine Rollen (Backoffice vs. Trainer)
   - API ist aktuell komplett offen!

3. **Produktions-Datenbank** ❌
   - Aktuell nur SQLite (nicht für Production geeignet)
   - Migration zu PostgreSQL erforderlich
   - Backup-Strategie fehlt

4. **Deployment-Konfiguration** ❌
   - Kein `.env` für Production-Secrets
   - Keine Docker/Container-Konfiguration
   - Kein Prozess-Manager (Supervisor/systemd) Setup
   - Keine NGINX/Reverse-Proxy-Konfiguration
   - Kein SSL/HTTPS-Setup

5. **E-Mail-Integration** ❌
   - SMTP-Konfiguration pro Marke nicht implementiert
   - Kein tatsächlicher E-Mail-Versand
   - Template-Engine fehlt

6. **Monitoring & Logging** ❌
   - Keine strukturierten Logs
   - Kein Error-Tracking (z.B. Sentry)
   - Kein Health-Monitoring
   - Keine Performance-Metriken

### Wichtig für Vollständigkeit

7. **OpenAI/KI-Integration** 🟡
   - Nur Platzhalter-Code vorhanden
   - Keine echte API-Anbindung
   - Prompts nicht definiert

8. **Lexoffice-Integration** ❌
   - Nur Datenmodell-Felder vorhanden
   - API-Integration fehlt komplett

9. **Testing** ❌
   - Keine Unit-Tests
   - Keine Integration-Tests
   - Keine E2E-Tests

10. **Migration-System** ❌
    - Keine Alembic/Migration-Scripts
    - Schema-Änderungen nicht versioniert

---

## Technischer Stack

| Komponente | Technologie | Status |
|------------|-------------|--------|
| **Backend Framework** | FastAPI 0.110.0 | ✅ Implementiert |
| **Datenbank (Dev)** | SQLite | ✅ Funktional |
| **Datenbank (Prod)** | PostgreSQL | ❌ Nicht konfiguriert |
| **ORM** | SQLAlchemy 2.0.25 | ✅ Implementiert |
| **API-Validierung** | Pydantic 2.6.1 | ✅ Implementiert |
| **Frontend** | Nicht definiert | ❌ Fehlt komplett |
| **Auth** | Nicht implementiert | ❌ Fehlt |
| **Deployment** | uvicorn | 🟡 Nur Development |
| **Container** | Docker | ❌ Nicht konfiguriert |

---

## Next Steps - Roadmap zum Go-Live

### Phase 1: Production-Ready Backend (2-3 Wochen)

#### Woche 1: Security & Infrastructure
- [ ] **Authentifizierung implementieren**
  - FastAPI-Users oder JWT-basiertes System
  - User-Model mit Rollen (Admin, Backoffice, Trainer)
  - Login/Logout-Endpoints
  - Password-Hashing (bcrypt)

- [ ] **PostgreSQL einrichten**
  - Alembic-Migration-System aufsetzen
  - Initial-Migration erstellen
  - Connection-Pooling konfigurieren
  - Umgebungsvariablen für DB-Credentials

- [ ] **Environment-Konfiguration**
  - `.env.example` erstellen
  - Production-Settings (SECRET_KEY, DB-URL, etc.)
  - SMTP-Konfiguration pro Marke
  - OpenAI API-Key Management

#### Woche 2: Deployment-Vorbereitung
- [ ] **Docker-Setup**
  - Dockerfile für FastAPI-App
  - docker-compose.yml (App + PostgreSQL)
  - Multi-stage Build für kleinere Images

- [ ] **Deployment auf alwaysdata**
  - PostgreSQL-Datenbank erstellen
  - Python-Environment (Poetry) einrichten
  - Gunicorn/Uvicorn als Service konfigurieren
  - NGINX Reverse-Proxy Setup
  - SSL-Zertifikat (Let's Encrypt)

- [ ] **Backup-Strategie**
  - Cronjob für tägliche DB-Backups
  - Backup-Rotation (7 Tage, 4 Wochen, 3 Monate)
  - Backup-Monitoring

#### Woche 3: Monitoring & Testing
- [ ] **Logging & Monitoring**
  - Strukturiertes Logging (JSON)
  - Log-Rotation
  - Error-Tracking (Sentry oder ähnlich)
  - Health-Check-Endpoint erweitern

- [ ] **Basic Tests**
  - pytest-Setup
  - Integration-Tests für kritische Endpoints
  - API-Contract-Tests

- [ ] **Dokumentation**
  - API-Dokumentation vervollständigen
  - Deployment-Anleitung
  - Umgebungsvariablen dokumentieren

### Phase 2: Frontend MVP (3-4 Wochen)

#### Option A: React Admin (Schnellste Lösung)
- [ ] **Setup**
  - React Admin installieren
  - API-Integration (REST-DataProvider)
  - Authentifizierung einbinden

- [ ] **Kern-Views**
  - Dashboard (Übersicht aktive Trainings)
  - Training-Liste & Detail-Ansicht
  - Kunden-/Trainer-Verwaltung
  - Marken-Konfiguration

- [ ] **Workflow-Features**
  - Status-Änderung per Drag & Drop
  - Task-Checklisten
  - Quick-Actions (E-Mail senden, etc.)

#### Option B: Next.js Custom (Flexibler)
- [ ] **Setup**
  - Next.js 14+ mit App Router
  - TailwindCSS oder shadcn/ui
  - API-Client (fetch/axios)

- [ ] **Dashboard & Views**
  - Responsive Layout
  - Server-Side Rendering für Performance
  - Client-Side State-Management (Zustand/Redux)

### Phase 3: Advanced Features (Nach Go-Live)

- [ ] **E-Mail-Integration**
  - SMTP-Versand implementieren
  - Template-Rendering (Jinja2)
  - E-Mail-Tracking

- [ ] **OpenAI-Integration**
  - E-Mail-Vorschläge generieren
  - Notiz-Zusammenfassungen
  - Intelligent Search

- [ ] **Lexoffice-Integration**
  - API-Client implementieren
  - Angebote/Rechnungen synchronisieren
  - Webhook für Status-Updates

- [ ] **Erweiterte Automatisierung**
  - Reminder-E-Mails (Cron-Jobs)
  - Automatische Status-Übergänge
  - Export-Funktionen (PDF, Excel)

---

## Deployment-Optionen

### Empfehlung: alwaysdata (wie in README erwähnt)

**Vorteile:**
- Managed PostgreSQL
- SSH-Zugang für Deployment
- Cronjob-Support für Backups
- Günstiges Hosting in Europa

**Setup-Steps:**
```bash
# 1. Repository klonen
git clone <repo-url> ~/trainings-backoffice

# 2. Poetry & Dependencies
cd ~/trainings-backoffice/backend
poetry install --no-dev

# 3. Umgebungsvariablen
cp .env.example .env
# DATABASE_URL=postgresql://user:pass@localhost/trainings_db editieren

# 4. Datenbank-Migration
poetry run alembic upgrade head
poetry run python -m app.seed_data

# 5. Service starten (via Supervisor/systemd)
poetry run gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Alternative: Docker-Deployment

**Vorteile:**
- Portabilität
- Einfaches Scaling
- Konsistente Umgebung

**Nachteile:**
- Mehr Overhead
- Benötigt Container-Hosting (Railway, Render, DigitalOcean)

---

## Geschätzte Timelines

| Phase | Aufwand | Timeline |
|-------|---------|----------|
| **Phase 1: Backend Production-Ready** | 40-60h | 2-3 Wochen |
| **Phase 2: Frontend MVP** | 60-80h | 3-4 Wochen |
| **Phase 3: Advanced Features** | 40-60h | 2-3 Wochen |
| **Gesamt bis vollständiger MVP** | **140-200h** | **7-10 Wochen** |

---

## Risiken & Blocker

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| **Keine Auth → API offen** | Sehr hoch | Kritisch | Phase 1 Woche 1 priorisieren |
| **SQLite in Production** | Hoch | Hoch | Sofort PostgreSQL-Migration |
| **Keine Backups** | Hoch | Kritisch | Backup-Strategie vor Go-Live |
| **Fehlende Tests** | Mittel | Mittel | Schrittweise aufbauen |
| **Keine Monitoring** | Mittel | Mittel | Basic-Logging sofort, Advanced später |

---

## Ressourcen-Bedarf

- **1 Backend-Entwickler** (FastAPI, PostgreSQL, Deployment) - 2-3 Wochen Vollzeit
- **1 Frontend-Entwickler** (React/Next.js) - 3-4 Wochen Vollzeit
- **Optional: DevOps-Support** (Deployment, Monitoring) - 1 Woche

**Oder:**
- **1 Fullstack-Entwickler** - 8-10 Wochen Vollzeit

---

## Empfehlungen

### Sofortmaßnahmen (Diese Woche)
1. ✅ **Authentifizierung implementieren** - Höchste Priorität!
2. ✅ **PostgreSQL aufsetzen** - SQLite ist nicht production-ready
3. ✅ **Environment-Variablen dokumentieren** - `.env.example` erstellen

### Kurzfristig (Nächste 2 Wochen)
4. ✅ **Deployment-Scripts** - Automatisiertes Deployment einrichten
5. ✅ **Monitoring** - Basic Logging & Error-Tracking
6. ✅ **Backup-Strategie** - Automatisierte DB-Backups

### Mittelfristig (Nächste 4-6 Wochen)
7. ✅ **Frontend MVP** - React Admin für schnellsten Launch
8. ✅ **Testing** - Integration-Tests für kritische Flows
9. ✅ **Dokumentation** - User-Guide & Admin-Docs

### Langfristig (Nach Go-Live)
10. ✅ **E-Mail-Integration** - Automatisierte Kommunikation
11. ✅ **OpenAI-Features** - KI-gestützte Funktionen
12. ✅ **Lexoffice-Integration** - Automatisierte Rechnungsstellung

---

## Fazit

**Das Projekt ist ein solides MVP auf Backend-Seite**, aber noch **nicht produktionsreif**. Die kritischen Blocker sind:
- ❌ Fehlende Authentifizierung (Security-Risk!)
- ❌ SQLite statt PostgreSQL
- ❌ Kein Frontend
- ❌ Keine Deployment-Konfiguration

**Mit focused Entwicklung kann das System in 6-8 Wochen live gehen**, wenn:
1. Sofort mit Auth & PostgreSQL gestartet wird
2. Parallel Frontend entwickelt wird
3. Deployment-Infrastruktur vorbereitet wird

**Quick-Win für ersten Test:**
- React Admin als Frontend (1-2 Wochen)
- PostgreSQL-Migration (2-3 Tage)
- Basic Auth (3-5 Tage)
- Deployment auf alwaysdata (2-3 Tage)

→ **Minimaler MVP in 3-4 Wochen möglich!**
