"""
Skill: save_to_database
Description: Save a list of scholarships into a local SQLite database
             (scholarships.db), keyed by student email. Can also query
             saved scholarships for a given student.
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "scholarships.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scholarships (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_email TEXT    NOT NULL,
            name          TEXT    NOT NULL,
            amount        TEXT,
            eligibility   TEXT,
            deadline      TEXT,
            link          TEXT,
            saved_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_email, name)
        )
    """)
    conn.commit()
    return conn


def save_to_database(student_email: str, scholarships: list[dict]) -> str:
    """
    Save scholarships to the database for a student.

    Args:
        student_email: The student's email address (used as key)
        scholarships:  List of dicts with keys: name, amount, eligibility,
                       deadline, link

    Returns:
        Confirmation message string.
    """
    conn = _get_connection()
    saved = 0
    for s in scholarships:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO scholarships
                   (student_email, name, amount, eligibility, deadline, link)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    student_email,
                    s.get("name", ""),
                    s.get("amount", ""),
                    s.get("eligibility", ""),
                    s.get("deadline", ""),
                    s.get("link", ""),
                ),
            )
            saved += conn.execute("SELECT changes()").fetchone()[0]
        except sqlite3.Error as e:
            print(f"[save_to_database] DB error for {s.get('name')}: {e}")
    conn.commit()
    conn.close()
    msg = f"Saved {saved} new scholarships for {student_email} (duplicates ignored)."
    print(f"[save_to_database] {msg}")
    return msg


def query_from_database(student_email: str) -> list[dict]:
    """
    Query all saved scholarships for a student.

    Args:
        student_email: The student's email address

    Returns:
        List of scholarship dicts.
    """
    conn = _get_connection()
    rows = conn.execute(
        "SELECT name, amount, eligibility, deadline, link FROM scholarships WHERE student_email = ?",
        (student_email,),
    ).fetchall()
    conn.close()
    return [dict(zip(["name", "amount", "eligibility", "deadline", "link"], r)) for r in rows]


if __name__ == "__main__":
    # Quick test
    sample = [
        {
            "name": "Test Scholarship",
            "amount": "$1,000",
            "eligibility": "Malaysian CS students",
            "deadline": "Jan 2026",
            "link": "https://example.com",
        }
    ]
    print(save_to_database("test@example.com", sample))
    print(json.dumps(query_from_database("test@example.com"), indent=2))
