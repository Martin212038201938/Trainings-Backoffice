from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..models import Customer, Trainer, Training


def search_everywhere(session: Session, query: str):
    like_query = f"%{query.lower()}%"

    def _match(column):
        return func.lower(column).like(like_query)

    customers = (
        session.query(Customer)
        .filter(
            or_(
                _match(Customer.company_name),
                _match(Customer.contact_name),
                _match(Customer.contact_email),
                _match(Customer.tags),
            )
        )
        .all()
    )

    trainers = (
        session.query(Trainer)
        .filter(
            or_(
                _match(Trainer.first_name),
                _match(Trainer.last_name),
                _match(Trainer.email),
                _match(Trainer.tags),
            )
        )
        .all()
    )

    trainings = (
        session.query(Training)
        .filter(
            or_(
                _match(Training.title),
                _match(Training.location),
                _match(Training.communication_notes),
                _match(Training.internal_notes),
            )
        )
        .all()
    )

    return customers, trainers, trainings
