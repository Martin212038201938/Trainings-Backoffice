#!/usr/bin/env python3
"""
Setup script to create the noreply@yellow-boat.org mailbox via AlwaysData API.

This script should be run once during initial server setup to create the
system mailbox used for sending notifications.

Usage:
    python setup_noreply_mailbox.py

Environment variables required:
    ALWAYSDATA_API_KEY - Your AlwaysData API key
    ALWAYSDATA_ACCOUNT - Your AlwaysData account name (default: y-b)
    ALWAYSDATA_DOMAIN_ID - The domain ID for yellow-boat.org (or 0 to auto-detect)
"""

import os
import sys
import logging
import secrets
import string
import requests
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ALWAYSDATA_API_URL = "https://api.alwaysdata.com/v1"
PLATFORM_DOMAIN = "yellow-boat.org"
NOREPLY_EMAIL_NAME = "noreply"


def generate_secure_password(length: int = 24) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def get_api_auth() -> tuple:
    """Get API authentication tuple for requests."""
    api_key = os.environ.get('ALWAYSDATA_API_KEY', '')
    account = os.environ.get('ALWAYSDATA_ACCOUNT', 'y-b')

    if not api_key:
        raise ValueError("ALWAYSDATA_API_KEY environment variable is required")

    return (f"{api_key} account={account}", "")


def get_domain_id(domain_name: str) -> int:
    """Get the AlwaysData domain ID for a domain name."""
    try:
        response = requests.get(
            f"{ALWAYSDATA_API_URL}/domain/",
            auth=get_api_auth(),
            timeout=30
        )
        if response.status_code == 200:
            domains = response.json()
            for domain in domains:
                if domain.get("name") == domain_name:
                    return domain.get("id")
        logger.error(f"Domain {domain_name} not found. Available domains: {response.json()}")
        return 0
    except Exception as e:
        logger.error(f"Error getting domain ID: {e}")
        return 0


def list_existing_mailboxes() -> list:
    """List all existing mailboxes to check for duplicates."""
    try:
        response = requests.get(
            f"{ALWAYSDATA_API_URL}/mailbox/",
            auth=get_api_auth(),
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        logger.error(f"Error listing mailboxes: {e}")
        return []


def mailbox_exists(email_name: str, domain_id: int) -> bool:
    """Check if a mailbox already exists."""
    mailboxes = list_existing_mailboxes()
    for mailbox in mailboxes:
        if mailbox.get("name") == email_name:
            # Check if it's for the same domain
            mailbox_domain = mailbox.get("domain", {})
            if isinstance(mailbox_domain, dict):
                if mailbox_domain.get("id") == domain_id:
                    return True
            elif mailbox_domain == domain_id:
                return True
    return False


def create_noreply_mailbox(domain_id: int, password: str) -> tuple:
    """
    Create the noreply mailbox.

    Returns:
        Tuple of (success, email_address, password)
    """
    try:
        response = requests.post(
            f"{ALWAYSDATA_API_URL}/mailbox/",
            auth=get_api_auth(),
            json={
                "name": NOREPLY_EMAIL_NAME,
                "domain": domain_id,
                "password": password
            },
            timeout=30
        )

        if response.status_code in (200, 201):
            email_address = f"{NOREPLY_EMAIL_NAME}@{PLATFORM_DOMAIN}"
            logger.info(f"Successfully created mailbox: {email_address}")
            return True, email_address, password
        else:
            logger.error(f"Failed to create mailbox: {response.status_code} - {response.text}")
            return False, None, None

    except Exception as e:
        logger.error(f"Error creating mailbox: {e}")
        return False, None, None


def main():
    """Main setup function."""
    print("=" * 60)
    print("AlwaysData Mailbox Setup - noreply@yellow-boat.org")
    print("=" * 60)
    print()

    # Check for API key
    if not os.environ.get('ALWAYSDATA_API_KEY'):
        print("ERROR: ALWAYSDATA_API_KEY environment variable is required!")
        print()
        print("Get your API key from: https://admin.alwaysdata.com/token/")
        print()
        print("Then run:")
        print("  export ALWAYSDATA_API_KEY='your-api-key-here'")
        print("  python setup_noreply_mailbox.py")
        sys.exit(1)

    # Get domain ID
    domain_id = int(os.environ.get('ALWAYSDATA_DOMAIN_ID', 0))

    if domain_id == 0:
        print(f"Looking up domain ID for {PLATFORM_DOMAIN}...")
        domain_id = get_domain_id(PLATFORM_DOMAIN)

        if domain_id == 0:
            print(f"ERROR: Could not find domain {PLATFORM_DOMAIN}")
            print("Please check your AlwaysData account has this domain configured.")
            sys.exit(1)

        print(f"Found domain ID: {domain_id}")

    # Check if mailbox already exists
    print(f"Checking if {NOREPLY_EMAIL_NAME}@{PLATFORM_DOMAIN} already exists...")

    if mailbox_exists(NOREPLY_EMAIL_NAME, domain_id):
        print()
        print(f"Mailbox {NOREPLY_EMAIL_NAME}@{PLATFORM_DOMAIN} already exists!")
        print("No action needed.")
        print()
        print("If you need to reset the password, do this manually via:")
        print("  https://admin.alwaysdata.com/mailbox/")
        sys.exit(0)

    # Generate password and create mailbox
    password = generate_secure_password()

    print(f"Creating mailbox {NOREPLY_EMAIL_NAME}@{PLATFORM_DOMAIN}...")
    success, email_address, created_password = create_noreply_mailbox(domain_id, password)

    if success:
        print()
        print("=" * 60)
        print("SUCCESS! Mailbox created.")
        print("=" * 60)
        print()
        print("Mailbox Details:")
        print(f"  Email:    {email_address}")
        print(f"  Password: {created_password}")
        print()
        print("SMTP Settings:")
        print(f"  Host:     smtp-y-b.alwaysdata.net")
        print(f"  Port:     587")
        print(f"  TLS:      Yes")
        print(f"  Username: {email_address}")
        print(f"  Password: {created_password}")
        print()
        print("IMAP Settings:")
        print(f"  Host:     imap-y-b.alwaysdata.net")
        print(f"  Port:     993")
        print(f"  SSL:      Yes")
        print(f"  Username: {email_address}")
        print(f"  Password: {created_password}")
        print()
        print("IMPORTANT: Save this password securely!")
        print()
        print("Add these settings to your .env file:")
        print("-" * 60)
        print(f"SMTP_HOST=smtp-y-b.alwaysdata.net")
        print(f"SMTP_PORT=587")
        print(f"SMTP_USERNAME={email_address}")
        print(f"SMTP_PASSWORD={created_password}")
        print(f"SMTP_USE_TLS=true")
        print(f"SMTP_FROM_EMAIL={email_address}")
        print(f"SMTP_FROM_NAME=Yellow-Boat Academy")
        print(f"EMAIL_ENABLED=true")
        print()
        print(f"IMAP_HOST=imap-y-b.alwaysdata.net")
        print(f"IMAP_PORT=993")
        print(f"IMAP_USERNAME={email_address}")
        print(f"IMAP_PASSWORD={created_password}")
        print(f"IMAP_USE_SSL=true")
        print()
        print(f"ALWAYSDATA_DOMAIN_ID={domain_id}")
        print("-" * 60)
    else:
        print()
        print("ERROR: Failed to create mailbox.")
        print("Check the logs above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
