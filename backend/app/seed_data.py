from __future__ import annotations

from datetime import date, timedelta

from .database import Base, SessionLocal, engine
from .models import Brand, Customer, Trainer, Training, TrainingCatalogEntry
from .services import checklist

SEED_BRANDS = [
    {"name": "NeWoa", "slug": "newoa", "color": "#0050b3", "default_sender_email": "hello@newoa.de"},
    {"name": "Yellow-Boat KI-Trainings", "slug": "yellow-boat", "color": "#ffc107", "default_sender_email": "ahoi@yellow-boat.de"},
    {"name": "copilotenschule.de", "slug": "copilotenschule", "color": "#111"},
]

SEED_CUSTOMERS = [
    {"company_name": "Agile Scrum Group", "contact_name": "Laura Agile", "contact_email": "laura@agilescrum.io"},
    {"company_name": "Kommunales Bildungswerk e.V.", "contact_name": "Herr Müller", "contact_email": "mueller@kbw.de"},
]

SEED_TRAINERS = [
    {
        "first_name": "Saskia",
        "last_name": "Kaden",
        "email": "saskia.kaden@example.com",
        "preferred_topics": "Copilot, Change Management",
        "tags": "Copilot,Change",
        "default_day_rate": 1500.0,
    }
]

SEED_CATALOG = [
    {"title": "Microsoft 365 Copilot Grundlagen-Training", "training_type": "online", "default_format": "inhouse"},
    {"title": "GitHub Copilot für Softwareentwickler", "training_type": "online", "default_format": "inhouse"},
    {"title": "Copilot Strategie & Change Management Workshop", "training_type": "classroom", "default_format": "inhouse"},
]


def seed():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        if session.query(Brand).count() == 0:
            brands = [Brand(**data) for data in SEED_BRANDS]
            session.add_all(brands)
            session.flush()
        else:
            brands = session.query(Brand).all()

        if session.query(Customer).count() == 0:
            customers = []
            for idx, data in enumerate(SEED_CUSTOMERS):
                customer = Customer(**data)
                customer.brands.append(brands[idx % len(brands)])
                customers.append(customer)
            session.add_all(customers)
        else:
            customers = session.query(Customer).all()

        if session.query(Trainer).count() == 0:
            trainers = []
            for data in SEED_TRAINERS:
                trainer = Trainer(**data)
                trainer.brands = brands
                trainers.append(trainer)
            session.add_all(trainers)
        else:
            trainers = session.query(Trainer).all()

        if session.query(TrainingCatalogEntry).count() == 0:
            session.add_all(TrainingCatalogEntry(**data) for data in SEED_CATALOG)

        session.commit()

        if session.query(Training).count() == 0 and customers and brands and trainers:
            training = Training(
                title="Pilot Copilot-Training",
                training_type="online",
                training_format="inhouse",
                brand_id=brands[0].id,
                customer_id=customers[0].id,
                trainer_id=trainers[0].id,
                status="planning",
                start_date=date.today() + timedelta(days=21),
                end_date=date.today() + timedelta(days=21),
                timezone="Europe/Berlin",
                contact_person=customers[0].contact_name,
            )
            training.tasks = checklist.generate_tasks(training)
            session.add(training)
            session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    seed()
