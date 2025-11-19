# Trainings-Backoffice

Eine modulare, API-orientierte Backoffice-Plattform für die Verwaltung mehrerer Trainingsmarken (NeWoa, Yellow-Boat, copilotenschule.de etc.).

## Features

### Core Features
- **FastAPI-Backend** mit SQLAlchemy-Datenmodell für Marken, Kunden, Trainer, Trainings, Aufgaben und Vorlagen
- **Mandantenfähigkeit**: Zuordnung von Kunden und Trainern zu beliebigen Marken
- **Trainings-Workflow** mit Status, Checklisten-Tasks (Online vs. Classroom) und Aktivitätenprotokoll
- **Globale Suche** über Kunden, Trainer und Trainings
- **Seed-Daten** für schnellen Einstieg mit Beispielinhalten

### Security & Authentication ✅ NEW
- **JWT-basierte Authentifizierung** mit secure token handling
- **Rollenbasierte Zugriffskontrolle** (Admin, Backoffice User, Trainer)
- **Password-Hashing** mit bcrypt
- **CORS-Konfiguration** für sichere Cross-Origin-Anfragen
- **Security Headers** (HSTS, X-Frame-Options, CSP, etc.)
- **Geschützte API-Endpoints** mit Authentifizierungspflicht

### AI-Integration (Optional)
- **E-Mail-Vorschläge** und Notiz-Zusammenfassungen via OpenAI API
- Erweiterbar für weitere KI-gestützte Features

## Projektstruktur

```
backend/
  app/
    config.py              # Environment & Settings
    database.py            # SQLAlchemy Engine & Session
    main.py               # FastAPI Entry Point
    core/
      security.py         # JWT & Password Hashing
      deps.py            # Auth Dependencies & Role Checks
      monitoring.py      # Health Checks & Metrics
    models/
      core.py           # Core Models (Brand, Customer, Trainer, Training)
      user.py           # User Model & Roles
    routers/
      auth.py           # Authentication Endpoints
      brands.py         # Brand Management (Admin only)
      customers.py      # Customer Management
      trainers.py       # Trainer Management
      trainings.py      # Training Management
      tasks.py          # Task Management
      catalog.py        # Training Catalog
      search.py         # Global Search
    schemas/
      auth.py           # Auth-related Schemas
      base.py           # Core Pydantic Schemas
    services/
      checklist.py      # Auto-Checklisten pro Trainingstyp
      ai.py            # OpenAI-Integration
  scripts/
    create_admin_user.py    # Admin User Setup
    deploy.sh               # Deployment Script
    setup_production.sh     # Production Setup
    migrate.sh             # Database Migration Script
  deploy/
    supervisor.conf        # Supervisor Configuration
    nginx_snippet.conf    # Nginx Configuration Reference
  alembic/
    env.py               # Alembic Environment
    versions/            # Database Migrations
  wsgi.py               # WSGI Entry Point
  gunicorn_config.py    # Gunicorn Configuration
  alembic.ini          # Alembic Configuration
  pyproject.toml       # Poetry Dependencies
```

## Quick Start

### Lokale Entwicklung

1. **Poetry installieren** (falls noch nicht vorhanden):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Dependencies installieren**:
   ```bash
   cd backend
   poetry install
   poetry shell
   ```

3. **Environment konfigurieren**:
   ```bash
   cp ../.env.example .env
   # Bearbeite .env und setze SECRET_KEY, DATABASE_URL, etc.
   ```

   Generiere einen sicheren SECRET_KEY:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

4. **Datenbank initialisieren**:
   ```bash
   # Option A: Automatisch mit Seed-Daten
   python -m app.seed_data

   # Option B: Mit Alembic Migrations
   alembic upgrade head
   python scripts/create_admin_user.py
   ```

5. **API starten**:
   ```bash
   uvicorn app.main:app --reload
   ```

   Die API ist unter folgenden URLs erreichbar:
   - **API**: http://localhost:8000
   - **Interactive Docs**: http://localhost:8000/docs
   - **ReDoc**: http://localhost:8000/redoc
   - **Health Check**: http://localhost:8000/health
   - **Version Info**: http://localhost:8000/version

## Authentication & Authorization

### User Roles

- **Admin**: Voller Zugriff auf alle Ressourcen, User Management, Brand Management
- **Backoffice User**: Lese-/Schreibzugriff auf Trainings, Kunden, Trainer
- **Trainer**: Nur Lesezugriff auf eigene zugewiesene Trainings

### API Authentication

Alle API-Endpoints (außer `/auth/*` und `/health`) benötigen einen gültigen JWT-Token.

**Login**:
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123456"
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Authenticated Request**:
```bash
curl http://localhost:8000/trainings \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Initial Admin User

Nach dem Setup wird ein Standard-Admin-User erstellt:
- **Username**: `admin`
- **Email**: `admin@trainings-backoffice.local`
- **Password**: `admin123456`

⚠️ **WICHTIG**: Ändere das Passwort sofort nach dem ersten Login!

## Production Deployment

Für detaillierte Deployment-Anleitungen siehe **[DEPLOYMENT.md](./DEPLOYMENT.md)**.

### Quick Deployment (AlwaysData)

1. **Initial Setup**:
   ```bash
   ssh y-b@ssh-y-b.alwaysdata.net
   cd /home/y-b
   git clone https://github.com/Martin212038201938/Trainings-Backoffice.git trainings-backoffice
   cd trainings-backoffice/backend
   chmod +x scripts/*.sh
   ./scripts/setup_production.sh
   ```

2. **Configure AlwaysData Site** (#993983):
   - Type: Python WSGI
   - Python Version: 3.11+
   - Application Path: `/home/y-b/trainings-backoffice/backend`
   - WSGI File: `wsgi.py`
   - WSGI Callable: `application`

3. **Deployment Updates**:
   ```bash
   cd /home/y-b/trainings-backoffice/backend
   ./scripts/deploy.sh
   ```

### Environment Variables (Production)

Erforderliche Environment-Variablen (siehe `.env.production.example`):

```bash
# Database
DATABASE_URL=postgresql://user:pass@postgresql-y-b.alwaysdata.net/y-b_trainings_backoffice

# Security
SECRET_KEY=<generate-with-secrets.token_urlsafe(32)>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=https://bo.yellow-plane.com

# Optional
OPENAI_API_KEY=your-key-here
```

## API Documentation

### Authentication Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/auth/login` | Login with username/password | No |
| POST | `/auth/register` | Register new user (Admin only) | Yes (Admin) |
| GET | `/auth/me` | Get current user info | Yes |
| PUT | `/auth/me` | Update current user | Yes |
| GET | `/auth/users` | List all users | Yes (Admin) |
| DELETE | `/auth/users/{id}` | Delete user | Yes (Admin) |

### Core Endpoints

| Resource | Endpoints | Permissions |
|----------|-----------|-------------|
| Brands | `/brands/*` | Admin (write), All (read) |
| Customers | `/customers/*` | Backoffice+ (write), All (read) |
| Trainers | `/trainers/*` | Backoffice+ (write), All (read) |
| Trainings | `/trainings/*` | Backoffice+ (write), Trainer (read own) |
| Tasks | `/tasks/*` | Backoffice+ |
| Catalog | `/catalog/*` | Backoffice+ (write), All (read) |
| Search | `/search` | All authenticated users |

Vollständige API-Dokumentation: https://bo.yellow-plane.com/docs

## Database Migrations

### Create Migration

```bash
cd backend
poetry run alembic revision --autogenerate -m "Description of changes"
```

### Apply Migrations

```bash
# Production
./scripts/migrate.sh

# Development
alembic upgrade head
```

### Rollback Migration

```bash
alembic downgrade -1
```

## Testing

```bash
cd backend
poetry run pytest
```

## Code Quality

```bash
# Formatting
poetry run black app/

# Linting
poetry run ruff check app/
```

## Monitoring

### Health Checks

```bash
# Application health with DB check
curl https://bo.yellow-plane.com/health

# Version and build info
curl https://bo.yellow-plane.com/version
```

### Logs

```bash
# Application logs
tail -f /home/y-b/trainings-backoffice/logs/error.log

# Access logs
tail -f /home/y-b/trainings-backoffice/logs/access.log

# Supervisor logs
tail -f /home/y-b/trainings-backoffice/logs/supervisor-stderr.log
```

## Security Best Practices

✅ **Implemented**:
- JWT-based authentication
- Password hashing with bcrypt
- Role-based access control
- CORS configuration
- Security headers (HSTS, X-Frame-Options, etc.)
- Input validation with Pydantic
- SQL injection protection with SQLAlchemy ORM

⚠️ **TODO**:
- Rate limiting for auth endpoints
- Two-factor authentication
- API key management
- Audit logging
- Automated security scanning

## Troubleshooting

### Common Issues

**"Could not validate credentials" Error**:
- Check if SECRET_KEY is set in .env
- Verify token hasn't expired
- Ensure Authorization header format: `Bearer <token>`

**Database Connection Error**:
- Verify DATABASE_URL in .env
- Check database is running
- Test connection with provided script

**Import Errors**:
- Run `poetry install` to install dependencies
- Check Python version (3.11+ required)
- Activate poetry shell: `poetry shell`

Für weitere Hilfe siehe [DEPLOYMENT.md - Troubleshooting](./DEPLOYMENT.md#troubleshooting).

## Roadmap

### Phase 1 ✅ (Completed)
- [x] FastAPI Backend Setup
- [x] SQLAlchemy Models
- [x] REST API Endpoints
- [x] JWT Authentication
- [x] Role-based Authorization
- [x] Database Migrations (Alembic)
- [x] Production Deployment Setup

### Phase 2 (In Progress)
- [ ] Frontend (React/Next.js)
- [ ] Enhanced API Documentation
- [ ] Automated Testing Suite
- [ ] Rate Limiting & Throttling

### Phase 3 (Planned)
- [ ] Email Notifications & Reminders
- [ ] Lexoffice Integration
- [ ] Advanced Reporting
- [ ] File Upload & Management
- [ ] Calendar Integration
- [ ] Two-Factor Authentication
- [ ] Audit Logging

### Phase 4 (Future)
- [ ] Mobile App
- [ ] Real-time Notifications (WebSockets)
- [ ] Advanced AI Features
- [ ] Multi-language Support
- [ ] Custom Workflows

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -am 'Add new feature'`
4. Push to branch: `git push origin feature/my-feature`
5. Submit a Pull Request

## License

Proprietary - All rights reserved.

## Support

Für Fragen oder Probleme:
- Deployment-Probleme: siehe [DEPLOYMENT.md](./DEPLOYMENT.md)
- API-Dokumentation: https://bo.yellow-plane.com/docs
- GitHub Issues: https://github.com/Martin212038201938/Trainings-Backoffice/issues

---

**Version**: 1.0.0
**Last Updated**: 2025-11-19
**Status**: Production Ready ✅
