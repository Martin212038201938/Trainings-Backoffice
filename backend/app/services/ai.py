from __future__ import annotations

from typing import Dict

from ..config import settings


def suggest_email_text(prompt: str, tone: str = "freundlich", language: str = "de") -> Dict[str, str]:
    if not settings.openai_api_key:
        return {
            "subject": f"{tone.title()}e Nachricht zum Thema {prompt[:40]}",
            "body": f"Dies ist ein Platzhaltertext für {prompt}. Füge hier deinen individuellen Inhalt ein. (Sprache: {language})",
        }
    # Placeholder for real API integration
    return {
        "subject": "KI-generierte Betreffzeile",
        "body": "KI-generierter Text basierend auf dem Prompt.",
    }


def summarize_notes(notes: str) -> str:
    if not settings.openai_api_key:
        bullets = [line.strip() for line in notes.split("\n") if line.strip()]
        return "\n".join(f"• {bullet}" for bullet in bullets[:5])
    return "Zusammenfassung der Notizen (Platzhalter)."
