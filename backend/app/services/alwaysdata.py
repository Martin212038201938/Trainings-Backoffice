"""AlwaysData API integration for managing email accounts."""
from __future__ import annotations

import logging
import secrets
import string
import requests
from typing import Optional, Tuple

from ..config import settings

logger = logging.getLogger(__name__)

# AlwaysData API configuration
ALWAYSDATA_API_URL = "https://api.alwaysdata.com/v1"


def generate_secure_password(length: int = 16) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def get_api_auth() -> Tuple[str, str]:
    """Get API authentication tuple for requests."""
    api_key = settings.alwaysdata_api_key
    account = settings.alwaysdata_account
    # AlwaysData uses format: "APIKEY account=accountname:" as username, empty password
    return (f"{api_key} account={account}", "")


def create_mailbox(
    email_name: str,
    domain_id: int,
    password: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Create a new mailbox/email address in AlwaysData.

    Args:
        email_name: The part before @ (e.g., 'mueller' for mueller@yellow-boat.org)
        domain_id: The AlwaysData domain ID
        password: Optional password (generated if not provided)

    Returns:
        Tuple of (success, email_address, password)
    """
    if not settings.alwaysdata_api_key:
        logger.warning("AlwaysData API key not configured")
        return False, None, None

    if not password:
        password = generate_secure_password()

    try:
        response = requests.post(
            f"{ALWAYSDATA_API_URL}/mailbox/",
            auth=get_api_auth(),
            json={
                "name": email_name,
                "domain": domain_id,
                "password": password
            },
            timeout=30
        )

        if response.status_code in (200, 201):
            data = response.json()
            email_address = f"{email_name}@{settings.platform_email_domain}"
            logger.info(f"Created mailbox: {email_address}")
            return True, email_address, password
        else:
            logger.error(f"Failed to create mailbox: {response.status_code} - {response.text}")
            return False, None, None

    except Exception as e:
        logger.error(f"Error creating mailbox: {e}")
        return False, None, None


def delete_mailbox(mailbox_id: int) -> bool:
    """Delete a mailbox from AlwaysData."""
    if not settings.alwaysdata_api_key:
        return False

    try:
        response = requests.delete(
            f"{ALWAYSDATA_API_URL}/mailbox/{mailbox_id}/",
            auth=get_api_auth(),
            timeout=30
        )
        return response.status_code in (200, 204)
    except Exception as e:
        logger.error(f"Error deleting mailbox: {e}")
        return False


def list_mailboxes() -> list:
    """List all mailboxes in the account."""
    if not settings.alwaysdata_api_key:
        return []

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


def get_domain_id(domain_name: str) -> Optional[int]:
    """Get the AlwaysData domain ID for a domain name."""
    if not settings.alwaysdata_api_key:
        return None

    try:
        response = requests.get(
            f"{ALWAYSDATA_API_URL}/domain/",
            auth=get_api_auth(),
            params={"name": domain_name},
            timeout=30
        )
        if response.status_code == 200:
            domains = response.json()
            for domain in domains:
                if domain.get("name") == domain_name:
                    return domain.get("id")
        return None
    except Exception as e:
        logger.error(f"Error getting domain ID: {e}")
        return None


def create_user_mailbox(last_name: str, existing_emails: list[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Create a mailbox for a user based on their last name.
    Handles duplicates by adding incrementing numbers.

    Args:
        last_name: User's last name
        existing_emails: List of existing platform emails to check for duplicates

    Returns:
        Tuple of (success, email_address, password)
    """
    if not settings.alwaysdata_api_key or not settings.alwaysdata_domain_id:
        logger.warning("AlwaysData API not fully configured")
        return False, None, None

    # Normalize last name for email
    email_name = last_name.lower().replace(' ', '-').replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')

    # Remove special characters
    email_name = ''.join(c for c in email_name if c.isalnum() or c == '-')

    if not email_name:
        email_name = "user"

    # Check for duplicates and add number if needed
    if existing_emails:
        base_email = f"{email_name}@{settings.platform_email_domain}"
        if base_email in existing_emails:
            counter = 1
            while f"{email_name}{counter}@{settings.platform_email_domain}" in existing_emails:
                counter += 1
            email_name = f"{email_name}{counter}"

    return create_mailbox(email_name, settings.alwaysdata_domain_id)


def send_credentials_email(to_email: str, platform_email: str, password: str, user_name: str) -> bool:
    """Send email with the new mailbox credentials to the user."""
    from .email import send_email

    subject = "Deine neue E-Mail-Adresse bei Yellow-Boat Academy"
    body = f"""Hallo {user_name},

dein Account bei Yellow-Boat Academy wurde eingerichtet!

Du hast jetzt eine eigene E-Mail-Adresse:
E-Mail: {platform_email}
Passwort: {password}

Du kannst diese E-Mail-Adresse im Backoffice-Portal nutzen.

SMTP-Server: smtp-y-b.alwaysdata.net (Port 587, TLS)
IMAP-Server: imap-y-b.alwaysdata.net (Port 993, SSL)

Bitte aendere dein Passwort nach dem ersten Login!

Viele Gruesse,
Das Yellow-Boat Academy Team
"""
    return send_email(to_email, subject, body)
