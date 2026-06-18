"""Pure-Python scholarship search and ranking — no LLM involved."""
import json
from datetime import date
from config import DATA_DIR


def load_student(student_id: str) -> dict:
    students = json.loads((DATA_DIR / "students.json").read_text(encoding="utf-8"))
    student = next((s for s in students if s["id"] == student_id), None)
    if not student:
        raise ValueError(f"Student '{student_id}' not found. Available: {[s['id'] for s in students]}")
    return student


def _days_until(deadline_str: str) -> int:
    try:
        return (date.fromisoformat(deadline_str) - date.today()).days
    except (ValueError, TypeError):
        return 999


def _score(scholarship: dict, student: dict) -> float:
    """Return eligibility score ≥0, or -1.0 if ineligible."""
    # Hard filter: GPA
    if student["gpa"] < scholarship.get("min_gpa", 0):
        return -1.0

    # Hard filter: nationality
    nationality = student.get("nationality", "").lower()
    eligible_nats = [n.lower() for n in scholarship.get("eligible_nationalities", ["all"])]
    if "all" not in eligible_nats and nationality not in eligible_nats:
        return -1.0

    # Hard filter: expired deadline
    days = _days_until(scholarship.get("deadline", "2099-01-01"))
    if days < 0:
        return -1.0

    score = 0.0
    student_field = student.get("field_of_study", "").lower()
    s_fields = [f.lower() for f in scholarship.get("fields", [])]
    interests = [i.lower() for i in student.get("interests", [])]
    description = scholarship.get("description", "").lower()

    # Field match — up to 40 pts
    if "all" in s_fields:
        score += 10
    elif any(student_field in f or f in student_field for f in s_fields):
        score += 40  # exact match
    elif any(interest in " ".join(s_fields) or interest in description for interest in interests):
        score += 25  # interest match
    else:
        score += 5   # general, still eligible

    # Amount — up to 20 pts (capped at $20k)
    score += min(scholarship.get("amount_usd", 0) / 1000, 20)

    # Deadline urgency — up to 10 pts
    if 30 <= days <= 180:
        score += 10
    elif days < 30:
        score += 7
    elif days <= 365:
        score += 5
    else:
        score += 2

    # Renewable bonus
    if scholarship.get("renewable", False):
        score += 2

    return round(score, 2)


def search_and_rank(student: dict, top_n: int = 10) -> list[dict]:
    """Return the top eligible scholarships ranked by score."""
    all_scholarships = json.loads((DATA_DIR / "scholarships.json").read_text(encoding="utf-8"))
    scored = [
        {**s, "_score": _score(s, student)}
        for s in all_scholarships
        if _score(s, student) >= 0
    ]
    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored[:top_n]
