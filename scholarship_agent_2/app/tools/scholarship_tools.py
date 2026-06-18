"""
Scholarship Agent tools — registered as an in-process MCP server.

All 9 tools are defined here:
  1. save_student_profile
  2. get_student_profile
  3. search_internal_scholarships
  4. search_web_scholarships
  5. check_eligibility
  6. rank_scholarships
  7. generate_essay
  8. get_deadlines
  9. send_email_notification
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
from claude_agent_sdk import tool, create_sdk_mcp_server

from app.db.session import db_session
from app.db.models import Student, Scholarship, Application, Email
from app.email.mailer import (
    send_email,
    build_recommendation_email,
    build_reminder_email,
    build_update_email,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


def _text(content: str) -> dict:
    """Wrap a string in MCP tool result format."""
    return {"content": [{"type": "text", "text": content}]}


def _json(data: Any) -> dict:
    """Wrap a JSON-serialisable object in MCP tool result format."""
    return _text(json.dumps(data, default=str, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# 1. save_student_profile
# ─────────────────────────────────────────────────────────────────────────────

@tool(
    "save_student_profile",
    "Create or update a student profile in the database. Returns the saved student record.",
    {
        "name": str,
        "email": str,
        "nationality": str,
        "course_interest": str,
        "academic_results": float,
        "income_level": str,  # "low" | "middle" | "high"
    },
)
async def save_student_profile(args: dict) -> dict:
    income = args.get("income_level", "middle")
    if income not in ("low", "middle", "high"):
        income = "middle"

    with db_session() as db:
        existing = db.query(Student).filter_by(email=args["email"]).first()
        if existing:
            existing.name = args["name"]
            existing.nationality = args["nationality"]
            existing.course_interest = args["course_interest"]
            existing.academic_results = float(args["academic_results"])
            existing.income_level = income
            student = existing
        else:
            student = Student(
                name=args["name"],
                email=args["email"],
                nationality=args["nationality"],
                course_interest=args["course_interest"],
                academic_results=float(args["academic_results"]),
                income_level=income,
            )
            db.add(student)
            db.flush()

        return _json({"status": "saved", "student": student.to_dict()})


# ─────────────────────────────────────────────────────────────────────────────
# 2. get_student_profile
# ─────────────────────────────────────────────────────────────────────────────

@tool(
    "get_student_profile",
    "Retrieve a student profile by student_id or email. Returns the student record or null.",
    {"identifier": str},  # student_id (int as str) or email
)
async def get_student_profile(args: dict) -> dict:
    identifier = args["identifier"]
    with db_session() as db:
        if identifier.isdigit():
            student = db.query(Student).filter_by(id=int(identifier)).first()
        else:
            student = db.query(Student).filter_by(email=identifier).first()

        if not student:
            return _json({"found": False, "student": None})
        return _json({"found": True, "student": student.to_dict()})


# ─────────────────────────────────────────────────────────────────────────────
# 3. search_internal_scholarships
# ─────────────────────────────────────────────────────────────────────────────

@tool(
    "search_internal_scholarships",
    (
        "Search the internal scholarship database. Filters: country, course, "
        "min_gpa, income_level, limit. Returns a list of scholarship records."
    ),
    {
        "country": str,
        "course": str,
        "min_gpa": float,
        "income_level": str,
        "limit": int,
    },
)
async def search_internal_scholarships(args: dict) -> dict:
    country = args.get("country", "")
    course = args.get("course", "")
    min_gpa = float(args.get("min_gpa", 0.0))
    income = args.get("income_level", "")
    limit = int(args.get("limit", 10))

    with db_session() as db:
        q = db.query(Scholarship).filter(Scholarship.deadline > datetime.utcnow())

        if country:
            q = q.filter(Scholarship.country.ilike(f"%{country}%"))
        if course:
            q = q.filter(Scholarship.course.ilike(f"%{course}%"))

        scholarships = q.order_by(Scholarship.deadline.asc()).limit(limit * 3).all()

        # Filter by GPA and income in Python (JSON column)
        results = []
        for s in scholarships:
            req = s.requirements or {}
            if min_gpa and req.get("min_gpa", 0) > min_gpa:
                continue
            if income and req.get("income_level") and req["income_level"] != income:
                continue
            results.append(s.to_dict())
            if len(results) >= limit:
                break

        return _json({"count": len(results), "scholarships": results})


# ─────────────────────────────────────────────────────────────────────────────
# 4. search_web_scholarships
# ─────────────────────────────────────────────────────────────────────────────

@tool(
    "search_web_scholarships",
    (
        "Search for scholarships on the web using the Serper API. "
        "Returns raw search results that Claude should summarise and verify."
    ),
    {"query": str, "num_results": int},
)
async def search_web_scholarships(args: dict) -> dict:
    query = args.get("query", "scholarships")
    num = int(args.get("num_results", 5))

    # Use Serper.dev (Google Search API) — replace with your preferred provider.
    serper_key = settings.SERPER_API_KEY if hasattr(settings, "SERPER_API_KEY") else ""

    if not serper_key:
        # Graceful fallback — return a helpful message so Claude can explain to the user.
        return _json({
            "note": (
                "Web search requires SERPER_API_KEY. "
                "Set it in .env to enable live web scholarship searches."
            ),
            "results": [],
        })

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
            json={"q": f"{query} scholarship site:.edu OR site:.gov OR site:.org", "num": num},
        )
        resp.raise_for_status()
        data = resp.json()

    results = [
        {
            "title": r.get("title"),
            "link": r.get("link"),
            "snippet": r.get("snippet"),
        }
        for r in data.get("organic", [])[:num]
    ]
    return _json({"count": len(results), "results": results})


# ─────────────────────────────────────────────────────────────────────────────
# 5. check_eligibility
# ─────────────────────────────────────────────────────────────────────────────

@tool(
    "check_eligibility",
    (
        "Check whether a specific student is eligible for a specific scholarship. "
        "Returns eligible (bool), score (0–1), and a list of reasons."
    ),
    {"student_id": int, "scholarship_id": int},
)
async def check_eligibility(args: dict) -> dict:
    student_id = int(args["student_id"])
    scholarship_id = int(args["scholarship_id"])

    with db_session() as db:
        student = db.query(Student).filter_by(id=student_id).first()
        scholarship = db.query(Scholarship).filter_by(id=scholarship_id).first()

        if not student:
            return _json({"eligible": False, "score": 0, "reasons": ["Student not found"]})
        if not scholarship:
            return _json({"eligible": False, "score": 0, "reasons": ["Scholarship not found"]})

        req = scholarship.requirements or {}
        reasons = []
        score_components = []

        # GPA check
        min_gpa = req.get("min_gpa", 0)
        if student.academic_results >= min_gpa:
            score_components.append(1.0)
            reasons.append(f"✅ GPA {student.academic_results:.1f} meets minimum {min_gpa:.1f}")
        else:
            score_components.append(0.0)
            reasons.append(f"❌ GPA {student.academic_results:.1f} below minimum {min_gpa:.1f}")

        # Nationality check
        allowed_nationalities = req.get("nationalities", [])
        if not allowed_nationalities or student.nationality in allowed_nationalities:
            score_components.append(1.0)
            reasons.append("✅ Nationality eligible")
        else:
            score_components.append(0.0)
            reasons.append(f"❌ Nationality '{student.nationality}' not in allowed list")

        # Income check
        allowed_income = req.get("income_levels", [])
        if not allowed_income or student.income_level in allowed_income:
            score_components.append(1.0)
            reasons.append("✅ Income level eligible")
        else:
            score_components.append(0.0)
            reasons.append(f"❌ Income level '{student.income_level}' not eligible")

        # Course relevance
        if (
            student.course_interest.lower() in scholarship.course.lower()
            or scholarship.course.lower() in student.course_interest.lower()
        ):
            score_components.append(1.0)
            reasons.append("✅ Course matches scholarship field")
        else:
            score_components.append(0.5)
            reasons.append("⚠️  Course may be related — please verify")

        # Deadline check
        if scholarship.deadline > datetime.utcnow():
            score_components.append(1.0)
        else:
            score_components.append(0.0)
            reasons.append("❌ Scholarship deadline has passed")

        score = sum(score_components) / len(score_components)
        eligible = score >= 0.6 and (scholarship.deadline > datetime.utcnow())

        return _json({
            "eligible": eligible,
            "score": round(score, 3),
            "reasons": reasons,
            "student_name": student.name,
            "scholarship_name": scholarship.name,
        })


# ─────────────────────────────────────────────────────────────────────────────
# 6. rank_scholarships
# ─────────────────────────────────────────────────────────────────────────────

@tool(
    "rank_scholarships",
    (
        "Rank a list of eligible scholarships for a student. "
        "Combines match_score (60%) and deadline urgency (40%). "
        "Pass a list of {scholarship_id, match_score} dicts."
    ),
    {"student_id": int, "candidates": list},
)
async def rank_scholarships(args: dict) -> dict:
    candidates = args.get("candidates", [])
    now = datetime.utcnow()
    max_days = 365

    ranked = []
    with db_session() as db:
        for c in candidates:
            sid = int(c.get("scholarship_id", 0))
            match_score = float(c.get("match_score", 0.5))

            scholarship = db.query(Scholarship).filter_by(id=sid).first()
            if not scholarship:
                continue

            days_left = max(0, (scholarship.deadline - now).days)
            deadline_urgency = 1.0 - min(days_left / max_days, 1.0)

            composite = (match_score * 0.6) + (deadline_urgency * 0.4)
            urgency_label = (
                "CRITICAL" if days_left <= 7
                else "URGENT" if days_left <= 30
                else "NORMAL"
            )

            ranked.append({
                **scholarship.to_dict(),
                "match_score": round(match_score, 3),
                "deadline_urgency": round(deadline_urgency, 3),
                "composite_score": round(composite, 3),
                "days_left": days_left,
                "urgency": urgency_label,
            })

    ranked.sort(key=lambda x: x["composite_score"], reverse=True)
    return _json({"count": len(ranked), "ranked_scholarships": ranked})


# ─────────────────────────────────────────────────────────────────────────────
# 7. generate_essay
# ─────────────────────────────────────────────────────────────────────────────

@tool(
    "generate_essay",
    (
        "Generate a personalised scholarship application essay for a student. "
        "Uses the student profile and scholarship details. Returns the essay text."
    ),
    {
        "student_id": int,
        "scholarship_id": int,
        "word_count": int,
        "extra_context": str,
    },
)
async def generate_essay(args: dict) -> dict:
    student_id = int(args["student_id"])
    scholarship_id = int(args["scholarship_id"])
    word_count = int(args.get("word_count", 600))
    extra = args.get("extra_context", "")

    with db_session() as db:
        student = db.query(Student).filter_by(id=student_id).first()
        scholarship = db.query(Scholarship).filter_by(id=scholarship_id).first()

        if not student or not scholarship:
            return _json({"error": "Student or scholarship not found"})

        # The agent (Claude) will compose the actual essay.
        # We return a structured prompt so Claude knows what to write.
        prompt = f"""
Write a compelling scholarship application essay (~{word_count} words) for:

Student: {student.name}
Nationality: {student.nationality}
Field of Study: {student.course_interest}
Academic Results: {student.academic_results} GPA
Income Level: {student.income_level}
{f'Additional context: {extra}' if extra else ''}

Scholarship: {scholarship.name}
Provider: {scholarship.provider}
Country: {scholarship.country}
Field: {scholarship.course}
Description: {scholarship.description or 'N/A'}

Structure: Hook → Personal Background → Academic Goals → Why This Scholarship → Conclusion

IMPORTANT: Only use the information provided above. Do not invent achievements or credentials.
        """.strip()

        # Save essay placeholder to application record
        app = (
            db.query(Application)
            .filter_by(student_id=student_id, scholarship_id=scholarship_id)
            .first()
        )
        if app:
            app.essay = f"[GENERATED — see content below]\n\n{prompt}"

        return _json({
            "instruction": "Use the following prompt to write the essay directly in your response.",
            "essay_prompt": prompt,
        })


# ─────────────────────────────────────────────────────────────────────────────
# 8. get_deadlines
# ─────────────────────────────────────────────────────────────────────────────

@tool(
    "get_deadlines",
    (
        "Get upcoming scholarship deadlines for a student. "
        "Returns deadlines sorted by urgency. Optional: days_ahead filter."
    ),
    {"student_id": int, "days_ahead": int},
)
async def get_deadlines(args: dict) -> dict:
    student_id = int(args["student_id"])
    days_ahead = int(args.get("days_ahead", 90))
    cutoff = datetime.utcnow() + timedelta(days=days_ahead)
    now = datetime.utcnow()

    with db_session() as db:
        apps = (
            db.query(Application)
            .filter(
                Application.student_id == student_id,
                Application.status.in_(["pending", "in_progress"]),
            )
            .all()
        )

        results = []
        for app in apps:
            scholarship = db.query(Scholarship).filter_by(id=app.scholarship_id).first()
            if not scholarship or scholarship.deadline > cutoff:
                continue

            days_left = max(0, (scholarship.deadline - now).days)
            results.append({
                "application_id": app.id,
                "scholarship_id": scholarship.id,
                "scholarship_name": scholarship.name,
                "provider": scholarship.provider,
                "deadline": scholarship.deadline.isoformat(),
                "days_left": days_left,
                "urgency": (
                    "CRITICAL" if days_left <= 7
                    else "URGENT" if days_left <= 30
                    else "NORMAL"
                ),
                "application_status": app.status,
            })

        results.sort(key=lambda x: x["days_left"])
        return _json({"count": len(results), "deadlines": results})


# ─────────────────────────────────────────────────────────────────────────────
# 9. send_email_notification
# ─────────────────────────────────────────────────────────────────────────────

@tool(
    "send_email_notification",
    (
        "Send an email notification to a student. "
        "Types: 'recommendation' (scholarship list), 'reminder' (deadline), 'update' (status change). "
        "Returns success status and stored email_id."
    ),
    {
        "student_id": int,
        "email_type": str,  # recommendation | reminder | update
        "scholarships": list,  # used for recommendation type
        "scholarship_name": str,  # used for reminder / update
        "days_left": int,  # used for reminder
        "new_status": str,  # used for update
    },
)
async def send_email_notification(args: dict) -> dict:
    student_id = int(args["student_id"])
    email_type = args.get("email_type", "recommendation")

    with db_session() as db:
        student = db.query(Student).filter_by(id=student_id).first()
        if not student:
            return _json({"success": False, "error": "Student not found"})

        if email_type == "recommendation":
            scholarships = args.get("scholarships", [])
            subject = f"🎓 Your Scholarship Recommendations — {len(scholarships)} matches found"
            html = build_recommendation_email(student.name, scholarships)

        elif email_type == "reminder":
            scholarship_name = args.get("scholarship_name", "your scholarship")
            days_left = int(args.get("days_left", 0))
            subject = f"⏰ Deadline Reminder: {scholarship_name} — {days_left} day(s) left"
            html = build_reminder_email(student.name, scholarship_name, days_left)

        elif email_type == "update":
            scholarship_name = args.get("scholarship_name", "your scholarship")
            new_status = args.get("new_status", "updated")
            subject = f"📬 Application Update: {scholarship_name}"
            html = build_update_email(student.name, scholarship_name, new_status)

        else:
            return _json({"success": False, "error": f"Unknown email_type: {email_type}"})

    result = send_email(
        student_id=student_id,
        to_email=student.email,
        subject=subject,
        html_body=html,
        email_type=email_type,
    )
    return _json(result)


# ─────────────────────────────────────────────────────────────────────────────
# MCP Server factory
# ─────────────────────────────────────────────────────────────────────────────

def create_scholarship_mcp_server():
    """Bundle all 9 tools into a single in-process MCP server."""
    return create_sdk_mcp_server(
        name="scholarship-tools",
        version="1.0.0",
        tools=[
            save_student_profile,
            get_student_profile,
            search_internal_scholarships,
            search_web_scholarships,
            check_eligibility,
            rank_scholarships,
            generate_essay,
            get_deadlines,
            send_email_notification,
        ],
    )
