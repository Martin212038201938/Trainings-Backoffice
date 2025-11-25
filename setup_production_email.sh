#!/bin/bash
# Setup script for production email configuration
# Run this on the AlwaysData server via SSH

echo "=== Yellow-Boat Email Setup ==="
echo ""

cd /home/y-b/trainings-backoffice/backend

# Backup existing .env
if [ -f .env ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo "✓ Backup der .env erstellt"
fi

# Add email configuration to .env
cat >> .env << 'ENVEOF'

# Email Settings (SMTP) - Added by setup script
EMAIL_ENABLED=true
SMTP_HOST=smtp-y-b.alwaysdata.net
SMTP_PORT=587
SMTP_USERNAME=noreply@yellow-boat.org
SMTP_PASSWORD=YB2025!SecureNoreply#Pass
SMTP_USE_TLS=true
SMTP_FROM_EMAIL=noreply@yellow-boat.org
SMTP_FROM_NAME=Yellow-Boat Academy

# AlwaysData API - Added by setup script
ALWAYSDATA_API_KEY=c54e97aec93546e680e186ce20417601
ALWAYSDATA_ACCOUNT=y-b
ALWAYSDATA_DOMAIN_ID=121892
ENVEOF

echo "✓ Email-Konfiguration zu .env hinzugefügt"

# Pull latest code
cd /home/y-b/trainings-backoffice
echo ""
echo "=== Neuesten Code holen ==="
git pull origin main

# Reload app
echo ""
echo "=== App neu laden ==="
touch /home/y-b/trainings-backoffice/backend/app/flask_app.py

echo ""
echo "=== Setup abgeschlossen ==="
echo ""
echo "Bitte teste jetzt:"
echo "1. Neue Trainer-Bewerbung einreichen"
echo "2. Im Admin-Bereich unter 'Neue Trainer' prüfen"
echo "3. Bewerbung genehmigen und E-Mail-Versand prüfen"
