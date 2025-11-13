from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, List

from ..models import Training, TrainingTask

ONLINE_DEFAULT_TASKS = (
    "Teams-Termin anlegen",
    "Besprechungslink einfügen",
    "Teilnehmer-Einladungen verschicken",
)

CLASSROOM_DEFAULT_TASKS = (
    "Location final bestätigen",
    "Catering bestellen",
    "Wegbeschreibung und Parkhinweise senden",
)


def _base_tasks_for_training(training: Training) -> Iterable[str]:
    if training.training_type == "online":
        return ONLINE_DEFAULT_TASKS
    return CLASSROOM_DEFAULT_TASKS


def generate_tasks(training: Training, due_date: date | None = None) -> List[TrainingTask]:
    base_tasks = list(_base_tasks_for_training(training))
    tasks: List[TrainingTask] = []
    for title in base_tasks:
        tasks.append(
            TrainingTask(
                title=title,
                is_required=True,
                status="open",
                due_date=due_date or (training.start_date - timedelta(days=7) if training.start_date else None),
                assignee="Backoffice",
            )
        )
    return tasks
