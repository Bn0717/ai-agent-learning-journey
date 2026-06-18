import sqlite3
import pathlib

DB_PATH = pathlib.Path('scholarship.db')


def track_scholarship(
    student_id: str,
    scholarship_name: str,
    provider: str,
    deadline: str = None,
    application_link: str = None,
    status: str = 'interested',
) -> dict:
    """Save a scholarship to the student's tracker in the database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO tracked_scholarships (student_id, scholarship_name, provider, deadline, application_link, status) VALUES (?,?,?,?,?,?)",
        (student_id, scholarship_name, provider, deadline, application_link, status),
    )
    conn.commit()
    track_id = c.lastrowid
    conn.close()
    return {
        "tracked": True,
        "id": track_id,
        "message": f"'{scholarship_name}' saved to tracker for student {student_id}",
    }


def get_tracked_scholarships(student_id: str) -> list:
    """Retrieve all tracked scholarships for a student."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM tracked_scholarships WHERE student_id = ? ORDER BY created_at DESC",
        (student_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_scholarship_status(track_id: int, status: str) -> dict:
    """Update the application status of a tracked scholarship."""
    valid = ('interested', 'applied', 'pending', 'awarded', 'rejected')
    if status not in valid:
        return {"error": f"Invalid status. Must be one of: {list(valid)}"}
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE tracked_scholarships SET status = ? WHERE id = ?", (status, track_id))
    conn.commit()
    conn.close()
    return {"id": track_id, "status": status, "updated": True}
