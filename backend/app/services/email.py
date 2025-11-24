"""Email service for sending notifications."""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Send a plain text email.

    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body (plain text)

    Returns:
        True if email was sent successfully, False otherwise
    """
    if not settings.email_enabled:
        logger.info(f"Email disabled - would send to {to_email}: {subject}")
        return False

    if not settings.smtp_host or not settings.smtp_from_email:
        logger.warning("SMTP not configured - email not sent")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        if settings.smtp_use_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port)

        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)

        server.sendmail(settings.smtp_from_email, to_email, msg.as_string())
        server.quit()

        logger.info(f"Email sent successfully to {to_email}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


# ============== Email Templates ==============

def send_welcome_email(user_email: str, username: str) -> bool:
    """Send welcome email to newly registered user."""
    subject = "Willkommen bei Yellow-Boat Academy"
    body = f"""Hallo {username},

willkommen bei Yellow-Boat Academy!

Dein Account wurde erfolgreich erstellt. Du kannst dich jetzt im Backoffice anmelden.

Bei Fragen stehen wir dir gerne zur Verfuegung.

Viele Gruesse,
Das Yellow-Boat Academy Team
"""
    return send_email(user_email, subject, body)


def send_trainer_application_received(trainer_email: str, trainer_name: str) -> bool:
    """Send confirmation email when trainer application is received."""
    subject = "Deine Bewerbung ist eingegangen"
    body = f"""Hallo {trainer_name},

vielen Dank fuer deine Bewerbung als Trainer bei Yellow-Boat Academy!

Wir haben deine Unterlagen erhalten und werden diese in Kuerze pruefen.
Du erhaeltst eine weitere Benachrichtigung, sobald wir deine Bewerbung bearbeitet haben.

Bei Fragen stehen wir dir gerne zur Verfuegung.

Viele Gruesse,
Das Yellow-Boat Academy Team
"""
    return send_email(trainer_email, subject, body)


def send_trainer_application_accepted(trainer_email: str, trainer_name: str) -> bool:
    """Send email when trainer application is accepted."""
    subject = "Deine Bewerbung wurde angenommen"
    body = f"""Hallo {trainer_name},

herzlichen Glueckwunsch! Deine Bewerbung als Trainer bei Yellow-Boat Academy wurde angenommen.

Dein Trainer-Profil wurde angelegt und du wirst in Kuerze weitere Informationen zu den naechsten Schritten erhalten.

Wir freuen uns auf die Zusammenarbeit!

Viele Gruesse,
Das Yellow-Boat Academy Team
"""
    return send_email(trainer_email, subject, body)


def send_trainer_application_rejected(trainer_email: str, trainer_name: str, reason: Optional[str] = None) -> bool:
    """Send email when trainer application is rejected."""
    subject = "Rueckmeldung zu deiner Bewerbung"

    reason_text = ""
    if reason:
        reason_text = f"\n\nBegruendung: {reason}\n"

    body = f"""Hallo {trainer_name},

vielen Dank fuer dein Interesse an Yellow-Boat Academy.

Nach sorgfaeltiger Pruefung deiner Bewerbung muessen wir dir leider mitteilen,
dass wir dir derzeit keine Trainer-Position anbieten koennen.{reason_text}

Wir wuenschen dir fuer deinen weiteren Weg alles Gute.

Viele Gruesse,
Das Yellow-Boat Academy Team
"""
    return send_email(trainer_email, subject, body)


def send_training_status_update(
    recipient_email: str,
    recipient_name: str,
    training_title: str,
    old_status: str,
    new_status: str,
    training_id: int
) -> bool:
    """Send email when training status changes."""
    # Translate status names to German
    status_names = {
        "lead": "Lead",
        "appointment_scheduled": "Termin vereinbart",
        "initial_contact": "Erstkontakt",
        "proposal_sent": "Angebot gesendet",
        "trainer_outreach": "Trainer-Anfrage",
        "trainer_confirmed": "Trainer bestaetigt",
        "planning": "In Planung",
        "delivered": "Durchgefuehrt",
        "invoiced": "Abgerechnet"
    }

    old_status_name = status_names.get(old_status, old_status)
    new_status_name = status_names.get(new_status, new_status)

    subject = f"Training Status-Update: {training_title}"
    body = f"""Hallo {recipient_name},

der Status des Trainings "{training_title}" (ID: {training_id}) wurde aktualisiert:

Alter Status: {old_status_name}
Neuer Status: {new_status_name}

Du kannst die Details im Backoffice einsehen.

Viele Gruesse,
Das Yellow-Boat Academy Team
"""
    return send_email(recipient_email, subject, body)


def send_new_application_admin_notification(
    admin_email: str,
    trainer_name: str,
    trainer_email: str,
    application_id: int
) -> bool:
    """Send notification to admin when new trainer application is received."""
    subject = "Neue Trainer-Bewerbung eingegangen"
    body = f"""Hallo,

eine neue Trainer-Bewerbung ist eingegangen:

Name: {trainer_name}
E-Mail: {trainer_email}
Bewerbungs-ID: {application_id}

Bitte pruefe die Bewerbung im Admin-Bereich des Backoffice.

Viele Gruesse,
Yellow-Boat Academy System
"""
    return send_email(admin_email, subject, body)


def send_trainer_assigned_notification(
    trainer_email: str,
    trainer_name: str,
    training_title: str,
    training_date: str,
    customer_name: str
) -> bool:
    """Send notification to trainer when assigned to a training."""
    subject = f"Du wurdest einem Training zugewiesen: {training_title}"
    body = f"""Hallo {trainer_name},

du wurdest einem neuen Training zugewiesen:

Training: {training_title}
Datum: {training_date}
Kunde: {customer_name}

Bitte pruefe die Details im Backoffice und bestatige deine Verfuegbarkeit.

Viele Gruesse,
Das Yellow-Boat Academy Team
"""
    return send_email(trainer_email, subject, body)


def send_training_reminder(
    trainer_email: str,
    trainer_name: str,
    training_title: str,
    training_date: str,
    training_time: str,
    location: str,
    customer_name: str
) -> bool:
    """Send reminder email to trainer one day before training."""
    subject = f"Erinnerung: Morgen Training - {training_title}"
    body = f"""Hallo {trainer_name},

dies ist eine Erinnerung an dein Training morgen:

Training: {training_title}
Datum: {training_date}
Uhrzeit: {training_time}
Ort: {location}
Kunde: {customer_name}

Bitte stelle sicher, dass du alle notwendigen Materialien vorbereitet hast.

Bei Fragen oder Problemen kontaktiere uns bitte umgehend.

Viele Gruesse,
Das Yellow-Boat Academy Team
"""
    return send_email(trainer_email, subject, body)
