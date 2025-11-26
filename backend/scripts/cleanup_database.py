#!/usr/bin/env python3
"""
Database cleanup script - removes all applications, users and trainers except specified admin.

Usage on AlwaysData server:
    cd /home/y-b/trainings-backoffice/backend
    source venv/bin/activate  # if using virtualenv
    python scripts/cleanup_database.py

Usage locally (if DATABASE_URL is set):
    cd backend
    python scripts/cleanup_database.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Check if we have database access
try:
    from app.database import SessionLocal, engine
    from app.models import User, Trainer, TrainerRegistration, Training, Message
    from app.models.core import TrainerApplication, ActivityLog
    from sqlalchemy import text
except Exception as e:
    print(f"ERROR: Could not import database modules: {e}")
    print("\nMake sure you have:")
    print("  1. A valid .env file with DATABASE_URL")
    print("  2. All dependencies installed (pip install -r requirements.txt)")
    sys.exit(1)

KEEP_EMAIL = "martin@yellow-boat.com"


def cleanup_database():
    """Clean up the database, keeping only the specified admin user."""
    db = SessionLocal()

    try:
        print("=" * 60)
        print("Database Cleanup Script")
        print("=" * 60)
        print(f"Keeping user: {KEEP_EMAIL}")
        print()

        # Find the user to keep
        admin_user = db.query(User).filter(User.email == KEEP_EMAIL).first()
        admin_id = admin_user.id if admin_user else None

        if admin_user:
            print(f"Found admin user: {admin_user.username} (ID: {admin_id})")
        else:
            print(f"WARNING: User {KEEP_EMAIL} not found!")

        # 1. Show current state
        print("\n--- Current Database State ---")
        print(f"Users: {db.query(User).count()}")
        print(f"Trainers: {db.query(Trainer).count()}")
        print(f"TrainerRegistrations (Applications): {db.query(TrainerRegistration).count()}")
        print(f"TrainerApplications (for Trainings): {db.query(TrainerApplication).count()}")
        print(f"Messages: {db.query(Message).count()}")
        print(f"ActivityLogs: {db.query(ActivityLog).count()}")

        # List all trainer registrations
        print("\n--- Trainer Registrations (to be deleted) ---")
        registrations = db.query(TrainerRegistration).all()
        for reg in registrations:
            print(f"  - {reg.email} ({reg.first_name} {reg.last_name}) - Status: {reg.status}")

        # List all users
        print("\n--- Users ---")
        users = db.query(User).all()
        for user in users:
            keep = "(KEEP)" if user.email == KEEP_EMAIL else "(DELETE)"
            print(f"  - {user.email} ({user.username}) - Role: {user.role} {keep}")

        # Ask for confirmation
        print("\n" + "=" * 60)
        response = input("Proceed with cleanup? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return

        print("\n--- Starting Cleanup ---")

        # 2. Delete all TrainerApplications (for specific trainings)
        count = db.query(TrainerApplication).delete()
        print(f"Deleted {count} TrainerApplications")

        # 3. Delete all TrainerRegistrations (public applications)
        count = db.query(TrainerRegistration).delete()
        print(f"Deleted {count} TrainerRegistrations")

        # 4. Delete all Messages (except from/to admin)
        if admin_id:
            count = db.query(Message).filter(
                Message.sender_id != admin_id,
                Message.recipient_id != admin_id
            ).delete(synchronize_session=False)
        else:
            count = db.query(Message).delete()
        print(f"Deleted {count} Messages")

        # 5. Delete all ActivityLogs
        count = db.query(ActivityLog).delete()
        print(f"Deleted {count} ActivityLogs")

        # 6. Unassign trainers from trainings
        db.query(Training).update({Training.trainer_id: None})
        print("Unassigned all trainers from trainings")

        # 7. Delete all Trainers (except admin's trainer profile if exists)
        if admin_id:
            admin_trainer = db.query(Trainer).filter(Trainer.user_id == admin_id).first()
            if admin_trainer:
                count = db.query(Trainer).filter(Trainer.id != admin_trainer.id).delete()
                print(f"Deleted {count} Trainers (kept admin's trainer profile)")
            else:
                count = db.query(Trainer).delete()
                print(f"Deleted {count} Trainers")
        else:
            count = db.query(Trainer).delete()
            print(f"Deleted {count} Trainers")

        # 8. Delete all Users except admin
        if admin_id:
            count = db.query(User).filter(User.id != admin_id).delete()
        else:
            count = db.query(User).delete()
        print(f"Deleted {count} Users")

        # Commit changes
        db.commit()

        print("\n--- Final Database State ---")
        print(f"Users: {db.query(User).count()}")
        print(f"Trainers: {db.query(Trainer).count()}")
        print(f"TrainerRegistrations: {db.query(TrainerRegistration).count()}")
        print(f"TrainerApplications: {db.query(TrainerApplication).count()}")
        print(f"Messages: {db.query(Message).count()}")

        print("\n" + "=" * 60)
        print("Cleanup completed successfully!")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    cleanup_database()
