# Deployment Guide - Trainings Backoffice

Comprehensive deployment guide for the Trainings Backoffice FastAPI application on AlwaysData.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Configuration](#configuration)
4. [Database Setup](#database-setup)
5. [Application Deployment](#application-deployment)
6. [Deployment Updates](#deployment-updates)
7. [Troubleshooting](#troubleshooting)
8. [Rollback Procedure](#rollback-procedure)
9. [Monitoring](#monitoring)

---

## Prerequisites

### AlwaysData Account
- **Site ID**: #993983
- **Site Type**: Python WSGI
- **Domain**: yellow-boat.org
- **SSH Access**: Required for deployment

### Required Software (on AlwaysData)
- Python 3.11+
- Poetry (Python package manager)
- PostgreSQL client
- Git

### Database
- **Host**: postgresql-y-b.alwaysdata.net
- **Database**: y-b_trainings_backoffice
- **User**: y-b_trainings_backoffice

---

## Initial Setup

### 1. Clone the Repository

```bash
ssh y-b@ssh-y-b.alwaysdata.net
cd ~
git clone https://github.com/Martin212038201938/Trainings-Backoffice.git trainings-backoffice
cd trainings-backoffice
```

### 2. Run Initial Setup Script

```bash
cd backend
chmod +x scripts/*.sh
./scripts/setup_production.sh
```

This script will:
- Check Python version
- Install Poetry
- Create necessary directories
- Set up environment file
- Install dependencies
- Test database connection
- Run migrations
- Create admin user

### 3. Manual Steps After Setup

1. **Generate SECRET_KEY**:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Copy the output and update `.env` file:
   ```bash
   nano ~/.env
   # Update SECRET_KEY with the generated value
   ```

2. **Configure AlwaysData Site**:
   - Go to: https://admin.alwaysdata.com/site/
   - Select Site #993983
   - Configuration:
     - Type: Python WSGI
     - Python Version: 3.11
     - Application path: `/home/y-b/trainings-backoffice/backend`
     - WSGI file: `wsgi.py`
     - WSGI callable: `application`

3. **Set Environment Variables** (AlwaysData Control Panel):
   - Go to: Environment > Environment variables
   - Add all variables from `.env` file

---

## Configuration

### Environment Variables

Create/update `.env` file in project root:

```bash
# Application Settings
APP_NAME="Trainings Backoffice"
ENVIRONMENT=production

# Database Configuration
DATABASE_URL=postgresql://y-b_trainings_backoffice:PASSWORD@postgresql-y-b.alwaysdata.net/y-b_trainings_backoffice

# Authentication & Security
SECRET_KEY=your-secure-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS Configuration
CORS_ORIGINS=https://yellow-boat.org

# OpenAI API (optional)
OPENAI_API_KEY=your-openai-key-here

# Logging
LOG_LEVEL=INFO
GUNICORN_ACCESS_LOG=/home/y-b/trainings-backoffice/logs/access.log
GUNICORN_ERROR_LOG=/home/y-b/trainings-backoffice/logs/error.log
```

### Important Security Notes

⚠️ **CRITICAL**: Never commit `.env` file to Git!

✅ **Do**:
- Use strong SECRET_KEY (32+ characters, random)
- Rotate SECRET_KEY regularly
- Use environment-specific configurations
- Enable HTTPS only in production

❌ **Don't**:
- Use default SECRET_KEY
- Commit secrets to Git
- Share credentials via email/chat
- Use same SECRET_KEY across environments

---

## Database Setup

### Manual Migration

If you need to run migrations manually:

```bash
cd /home/y-b/trainings-backoffice/backend

# Check current migration status
poetry run alembic current

# View pending migrations
poetry run alembic history

# Run migrations
./scripts/migrate.sh
```

### Create Admin User

```bash
cd /home/y-b/trainings-backoffice/backend
poetry run python scripts/create_admin_user.py
```

Default credentials (change immediately!):
- Username: `admin`
- Email: `admin@trainings-backoffice.local`
- Password: `admin123456`

### Database Backup

**Before any migration**, create a backup:

```bash
# Via AlwaysData Control Panel
# Go to: Databases > y-b_trainings_backoffice > Backups > Create backup

# Or via command line (if you have access)
pg_dump -h postgresql-y-b.alwaysdata.net \
        -U y-b_trainings_backoffice \
        -d y-b_trainings_backoffice \
        > backup_$(date +%Y%m%d_%H%M%S).sql
```

---

## Application Deployment

### Supervisor Configuration (Process Management)

1. Copy supervisor config to AlwaysData:
   ```bash
   cp backend/deploy/supervisor.conf ~/.supervisor/conf.d/trainings-backoffice.conf
   ```

2. Update supervisor:
   ```bash
   supervisorctl reread
   supervisorctl update
   ```

3. Start application:
   ```bash
   supervisorctl start trainings-backoffice
   ```

4. Check status:
   ```bash
   supervisorctl status trainings-backoffice
   ```

### Manual Start (without Supervisor)

```bash
cd /home/y-b/trainings-backoffice/backend
poetry run gunicorn -c gunicorn_config.py app.main:app
```

---

## Deployment Updates

### Automated Deployment Script

For routine updates, use the deployment script:

```bash
cd /home/y-b/trainings-backoffice/backend
./scripts/deploy.sh
```

This script will:
1. Pull latest changes from Git
2. Install/update dependencies
3. Run database migrations (optional)
4. Restart the application
5. Run health check

### Manual Deployment Steps

If you prefer manual deployment:

```bash
# 1. Navigate to project
cd /home/y-b/trainings-backoffice

# 2. Stash local changes (if any)
git stash

# 3. Pull latest changes
git pull origin main

# 4. Update dependencies
cd backend
poetry install --no-dev

# 5. Run migrations
poetry run alembic upgrade head

# 6. Restart application
supervisorctl restart trainings-backoffice

# 7. Verify deployment
curl https://yellow-boat.org/health
curl https://yellow-boat.org/version
```

### Zero-Downtime Deployment

For zero-downtime deployments:

```bash
# 1. Start new workers with updated code
# 2. Wait for health check to pass
# 3. Stop old workers
# This is handled automatically by Gunicorn with --reload flag
```

---

## Troubleshooting

### Common Issues

#### 1. Application Won't Start

**Symptoms**: Supervisor shows "FATAL" status

**Check**:
```bash
# View supervisor logs
tail -f /home/y-b/trainings-backoffice/logs/supervisor-stderr.log

# Check Gunicorn logs
tail -f /home/y-b/trainings-backoffice/logs/error.log

# Test manually
cd /home/y-b/trainings-backoffice/backend
poetry run python -c "from app.main import app; print('OK')"
```

**Common causes**:
- Missing dependencies: `poetry install --no-dev`
- Wrong Python version: Check AlwaysData site settings
- Database connection issues: Verify DATABASE_URL in `.env`
- Import errors: Check logs for module not found errors

#### 2. Database Connection Errors

**Symptoms**: "could not connect to server" or "password authentication failed"

**Check**:
```bash
# Test database connection
poetry run python << EOF
from app.config import settings
from app.database import engine
try:
    with engine.connect() as conn:
        print("✅ Database connection OK")
except Exception as e:
    print(f"❌ Database error: {e}")
EOF
```

**Solutions**:
- Verify DATABASE_URL format: `postgresql://user:pass@host/dbname`
- Check database credentials in AlwaysData panel
- Ensure database is running
- Check firewall/network settings

#### 3. Migration Errors

**Symptoms**: "Target database is not up to date" or "Can't locate revision"

**Check**:
```bash
# Check current migration
poetry run alembic current

# View migration history
poetry run alembic history

# Check database state
poetry run alembic stamp head  # Use with caution!
```

**Solutions**:
- Review migration files in `alembic/versions/`
- Check for manual database changes
- Restore from backup if needed
- Create new migration: `alembic revision --autogenerate -m "description"`

#### 4. Authentication Issues

**Symptoms**: 401 Unauthorized errors

**Check**:
- SECRET_KEY is set correctly in `.env`
- Token expiration time (ACCESS_TOKEN_EXPIRE_MINUTES)
- User account is active
- Password is correct

**Test**:
```bash
# Test login endpoint
curl -X POST https://yellow-boat.org/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123456"
```

#### 5. Performance Issues

**Symptoms**: Slow response times, timeouts

**Check**:
```bash
# Check Gunicorn workers
ps aux | grep gunicorn

# View access logs
tail -f /home/y-b/trainings-backoffice/logs/access.log

# Monitor system resources
top
```

**Solutions**:
- Increase worker count in `gunicorn_config.py`
- Optimize database queries
- Add database indexes
- Enable caching
- Check for N+1 query problems

### Log Files

Important log files:
- Supervisor stderr: `/home/y-b/trainings-backoffice/logs/supervisor-stderr.log`
- Supervisor stdout: `/home/y-b/trainings-backoffice/logs/supervisor-stdout.log`
- Gunicorn access: `/home/y-b/trainings-backoffice/logs/access.log`
- Gunicorn error: `/home/y-b/trainings-backoffice/logs/error.log`

View logs:
```bash
# Tail all logs
tail -f /home/y-b/trainings-backoffice/logs/*.log

# Search for errors
grep -i error /home/y-b/trainings-backoffice/logs/*.log

# View last 100 lines
tail -n 100 /home/y-b/trainings-backoffice/logs/error.log
```

---

## Rollback Procedure

### Quick Rollback

If deployment fails, rollback to previous version:

```bash
cd /home/y-b/trainings-backoffice

# 1. Check Git log
git log --oneline -10

# 2. Revert to previous commit
git reset --hard <previous-commit-hash>

# 3. Reinstall dependencies
cd backend
poetry install --no-dev

# 4. Rollback database (if needed)
poetry run alembic downgrade -1

# 5. Restart application
supervisorctl restart trainings-backoffice
```

### Database Rollback

**If migration needs to be reverted**:

```bash
# 1. Restore database backup
psql -h postgresql-y-b.alwaysdata.net \
     -U y-b_trainings_backoffice \
     -d y-b_trainings_backoffice \
     < backup_20250119_120000.sql

# 2. Downgrade one migration
poetry run alembic downgrade -1

# Or downgrade to specific version
poetry run alembic downgrade <revision>
```

---

## Monitoring

### Health Checks

**Primary health check**:
```bash
curl https://yellow-boat.org/health
```

Expected response:
```json
{
  "status": "ok",
  "app": "Trainings Backoffice",
  "timestamp": "2025-11-19T14:30:00.000Z",
  "database": {
    "status": "healthy",
    "connected": true
  }
}
```

**Version info**:
```bash
curl https://yellow-boat.org/version
```

### Monitoring Checklist

Daily:
- [ ] Check health endpoint
- [ ] Review error logs
- [ ] Monitor response times
- [ ] Check disk space

Weekly:
- [ ] Review access logs
- [ ] Check for failed logins
- [ ] Monitor database size
- [ ] Review API usage

Monthly:
- [ ] Update dependencies
- [ ] Rotate logs
- [ ] Review security settings
- [ ] Create database backup

### Metrics to Monitor

1. **Application**:
   - Response time (p50, p95, p99)
   - Error rate (4xx, 5xx)
   - Request rate
   - Active workers

2. **Database**:
   - Connection pool usage
   - Query response time
   - Database size
   - Failed queries

3. **System**:
   - CPU usage
   - Memory usage
   - Disk usage
   - Network I/O

### Setting Up Monitoring (Optional)

Consider setting up:
- **Sentry**: Error tracking and monitoring
- **Prometheus**: Metrics collection
- **Grafana**: Metrics visualization
- **UptimeRobot**: Uptime monitoring
- **CloudWatch/DataDog**: Full monitoring solution

---

## Production Checklist

Before going to production:

### Security
- [ ] SECRET_KEY is strong and unique
- [ ] DATABASE_URL contains strong password
- [ ] CORS_ORIGINS is set to production domain only
- [ ] HTTPS is enabled and enforced
- [ ] Security headers are configured
- [ ] Default admin password is changed
- [ ] Debug mode is disabled
- [ ] Sensitive data is not logged

### Performance
- [ ] Database indexes are created
- [ ] Gunicorn worker count is optimized
- [ ] Static files are compressed
- [ ] Caching is configured (if needed)
- [ ] Connection pooling is enabled

### Reliability
- [ ] Database backups are automated
- [ ] Application logs are rotated
- [ ] Health checks are configured
- [ ] Error tracking is set up
- [ ] Monitoring is in place
- [ ] Rollback procedure is tested

### Documentation
- [ ] API documentation is up to date
- [ ] Deployment guide is reviewed
- [ ] Team has access to credentials
- [ ] On-call procedures are defined

---

## Support

For issues or questions:

1. Check this documentation first
2. Review application logs
3. Check AlwaysData status page
4. Contact team lead
5. Create GitHub issue with logs and error messages

---

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [AlwaysData Documentation](https://help.alwaysdata.com/)
- [Poetry Documentation](https://python-poetry.org/docs/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)

---

**Last Updated**: 2025-11-19
**Version**: 1.0.0
