"""
scripts/send_reminders.py — Send deadline reminder emails.

Run daily via cron:
    0 9 * * * cd /app && python scripts/send_reminders.py

Or with Docker:
    docker exec scholarship_agent python scripts/send_reminders.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.db.models import Student, Scholarship, Application
from app.email.mailer import send_email, build_reminder_email


def send_reminders(days_threshold: int = 30):
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        cutoff = now + timedelta(days=days_threshold)

        # Find active applications with approaching deadlines
        apps = (
            db.query(Application)
            .filter(Application.status.in_(["pending", "in_progress"]))
            .all()
        )

        sent = 0
        for app in apps:
            scholarship = db.query(Scholarship).filter_by(id=app.scholarship_id).first()
            if not scholarship:
                continue

            if not (now < scholarship.deadline <= cutoff):
                continue

            student = db.query(Student).filter_by(id=app.student_id).first()
            if not student:
                continue

            days_left = (scholarship.deadline - now).days
            html = build_reminder_email(student.name, scholarship.name, days_left)
            urgency = "CRITICAL" if days_left <= 7 else "URGENT" if days_left <= 14 else "REMINDER"

            result = send_email(
                student_id=student.id,
                to_email=student.email,
                subject=f"[{urgency}] Deadline in {days_left} days: {scholarship.name}",
                html_body=html,
                email_type="reminder",
            )

            if result["success"]:
                sent += 1
                print(f"✅ Sent reminder to {student.email} for '{scholarship.name}' ({days_left}d)")
            else:
                print(f"❌ Failed reminder to {student.email}: {result.get('error')}")

        print(f"\nDone. Sent {sent} reminder(s).")
    finally:
        db.close()


if __name__ == "__main__":
    send_reminders()
