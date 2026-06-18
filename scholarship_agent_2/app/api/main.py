"""
FastAPI server for the Scholarship Agent.

Endpoints:
  POST /api/v1/chat              — Agent chat (single turn)
  POST /api/v1/chat/stream       — Agent chat (SSE streaming)
  POST /api/v1/student           — Create / update student profile
  GET  /api/v1/student/{id}      — Get student profile
  GET  /api/v1/scholarships      — List scholarships (with filters)
  POST /api/v1/scholarships      — Create scholarship (admin)
  POST /api/v1/email/send        — Send email notification
  GET  /api/v1/health            — Health check
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db, create_tables
from app.db.models import Student, Scholarship, Application, Email
from app.agent.runner import run_agent, run_agent_stream, run_agent_with_session
from app.email.mailer import send_email, build_recommendation_email

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Scholarship Agent API",
    description="AI-powered scholarship discovery and application assistant",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Create tables on startup (dev only — use Alembic in production)."""
    create_tables()
    logger.info("Database tables ready.")


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[str]
    session_id: Optional[str]
    cost_usd: Optional[float]


class StudentCreate(BaseModel):
    name: str
    email: EmailStr
    nationality: str
    course_interest: str
    academic_results: float
    income_level: str = "middle"

    @field_validator("income_level")
    @classmethod
    def validate_income(cls, v: str) -> str:
        if v not in ("low", "middle", "high"):
            raise ValueError("income_level must be 'low', 'middle', or 'high'")
        return v

    @field_validator("academic_results")
    @classmethod
    def validate_gpa(cls, v: float) -> float:
        if not (0.0 <= v <= 4.0):
            raise ValueError("academic_results (GPA) must be between 0.0 and 4.0")
        return v


class ScholarshipCreate(BaseModel):
    name: str
    provider: str
    country: str
    course: str
    requirements: dict
    deadline: datetime
    amount: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None


class EmailSendRequest(BaseModel):
    student_id: int
    email_type: str  # recommendation | reminder | update
    scholarships: Optional[list[dict]] = None
    scholarship_name: Optional[str] = None
    days_left: Optional[int] = None
    new_status: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ─────────────────────────────────────────────────────────────────────────────
# Chat endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    """Single-turn agent chat."""
    session_id = body.session_id or str(uuid.uuid4())

    try:
        result = await run_agent_with_session(session_id=session_id, prompt=body.prompt)
        return ChatResponse(
            response=result["response"],
            tool_calls=result["tool_calls"],
            session_id=session_id,
            cost_usd=result.get("cost_usd"),
        )
    except Exception as exc:
        logger.exception("Agent error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/chat/stream")
async def chat_stream(body: ChatRequest):
    """Streaming agent chat (SSE)."""
    async def event_generator():
        try:
            async for chunk in run_agent_stream(body.prompt):
                # Server-sent events format
                yield f"data: {chunk}\n\n"
        except Exception as exc:
            yield f"data: [ERROR] {exc}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Student endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/student", status_code=201)
async def create_student(body: StudentCreate, db: Session = Depends(get_db)):
    """Create or update a student profile."""
    existing = db.query(Student).filter_by(email=body.email).first()
    if existing:
        existing.name = body.name
        existing.nationality = body.nationality
        existing.course_interest = body.course_interest
        existing.academic_results = body.academic_results
        existing.income_level = body.income_level
        db.commit()
        db.refresh(existing)
        return existing.to_dict()

    student = Student(**body.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student.to_dict()


@app.get("/api/v1/student/{student_id}")
async def get_student(student_id: int, db: Session = Depends(get_db)):
    """Retrieve a student by ID."""
    student = db.query(Student).filter_by(id=student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# Scholarship endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/scholarships")
async def list_scholarships(
    country: Optional[str] = Query(None),
    course: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """List scholarships with optional filters."""
    q = db.query(Scholarship).filter(Scholarship.deadline > datetime.utcnow())
    if country:
        q = q.filter(Scholarship.country.ilike(f"%{country}%"))
    if course:
        q = q.filter(Scholarship.course.ilike(f"%{course}%"))
    scholarships = q.order_by(Scholarship.deadline.asc()).limit(limit).all()
    return {"count": len(scholarships), "scholarships": [s.to_dict() for s in scholarships]}


@app.post("/api/v1/scholarships", status_code=201)
async def create_scholarship(body: ScholarshipCreate, db: Session = Depends(get_db)):
    """Create a new scholarship record (admin use)."""
    scholarship = Scholarship(**body.model_dump())
    db.add(scholarship)
    db.commit()
    db.refresh(scholarship)
    return scholarship.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# Email endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/email/send")
async def send_email_endpoint(body: EmailSendRequest, db: Session = Depends(get_db)):
    """Send an email notification to a student."""
    student = db.query(Student).filter_by(id=body.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if body.email_type == "recommendation":
        from app.email.mailer import build_recommendation_email
        html = build_recommendation_email(student.name, body.scholarships or [])
        subject = f"🎓 Your Scholarship Recommendations — {len(body.scholarships or [])} matches"
    elif body.email_type == "reminder":
        from app.email.mailer import build_reminder_email
        html = build_reminder_email(student.name, body.scholarship_name or "", body.days_left or 0)
        subject = f"⏰ Deadline Reminder: {body.scholarship_name}"
    elif body.email_type == "update":
        from app.email.mailer import build_update_email
        html = build_update_email(student.name, body.scholarship_name or "", body.new_status or "")
        subject = f"📬 Application Update: {body.scholarship_name}"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown email_type: {body.email_type}")

    result = send_email(
        student_id=body.student_id,
        to_email=student.email,
        subject=subject,
        html_body=html,
        email_type=body.email_type,
    )
    return result
