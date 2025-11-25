#!/bin/bash
# Setup script for production email configuration
# Run this on the AlwaysData server via SSH
#
# SECURITY NOTE: This script requires environment variables to be set.
# DO NOT hardcode secrets in this file!
#
# Required environment variables (set these before running):
#   SMTP_PASSWORD - The SMTP password for the email account
#   ALWAYSDATA_API_KEY - The AlwaysData API key
#
# Example usage:
#   export SMTP_PASSWORD="your_smtp_password_here"
#   export ALWAYSDATA_API_KEY="your_api_key_here"
#   ./setup_production_email.sh

echo "=== Yellow-Boat Email Setup ==="
echo ""

# Check required environment variables
if [ -z "$SMTP_PASSWORD" ]; then
    echo "ERROR: SMTP_PASSWORD environment variable is not set!"
    echo "Please set it before running this script:"
    echo "  export SMTP_PASSWORD='your_password_here'"
    exit 1
fi

if [ -z "$ALWAYSDATA_API_KEY" ]; then
    echo "ERROR: ALWAYSDATA_API_KEY environment variable is not set!"
    echo "Please set it before running this script:"
    echo "  export ALWAYSDATA_API_KEY='your_api_key_here'"
    exit 1
fi

cd /home/y-b/trainings-backoffice/backend

# Backup existing .env
if [ -f .env ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo "✓ Backup der .env erstellt"
fi

# Add email configuration to .env (secrets from environment variables)
cat >> .env << ENVEOF

# Email Settings (SMTP) - Added by setup script
EMAIL_ENABLED=true
SMTP_HOST=smtp-y-b.alwaysdata.net
SMTP_PORT=587
SMTP_USERNAME=noreply@yellow-boat.org
SMTP_PASSWORD=${SMTP_PASSWORD}
SMTP_USE_TLS=true
SMTP_FROM_EMAIL=noreply@yellow-boat.org
SMTP_FROM_NAME=Yellow-Boat Academy

# AlwaysData API - Added by setup script
ALWAYSDATA_API_KEY=${ALWAYSDATA_API_KEY}
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
