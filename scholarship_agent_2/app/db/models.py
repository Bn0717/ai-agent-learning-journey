"""
SQLAlchemy ORM models for the Scholarship Agent.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime,
    ForeignKey, Enum as SAEnum, JSON
)
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    nationality = Column(String(100), nullable=False)
    course_interest = Column(String(255), nullable=False)
    academic_results = Column(Float, nullable=False, comment="GPA on 4.0 scale or equivalent")
    income_level = Column(
        SAEnum("low", "middle", "high", name="income_level_enum"),
        nullable=False,
        default="middle",
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    applications = relationship("Application", back_populates="student", cascade="all, delete-orphan")
    emails = relationship("Email", back_populates="student", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "nationality": self.nationality,
            "course_interest": self.course_interest,
            "academic_results": self.academic_results,
            "income_level": self.income_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Scholarship(Base):
    __tablename__ = "scholarships"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    provider = Column(String(255), nullable=False)
    country = Column(String(100), nullable=False, index=True)
    course = Column(String(255), nullable=False)
    requirements = Column(JSON, nullable=False, comment="Dict: {min_gpa, nationality, income, etc.}")
    deadline = Column(DateTime, nullable=False, index=True)
    amount = Column(String(100), nullable=True, comment="e.g. '£10,000/year' or 'Full tuition'")
    description = Column(Text, nullable=True)
    source_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    applications = relationship("Application", back_populates="scholarship")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "country": self.country,
            "course": self.course,
            "requirements": self.requirements,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "amount": self.amount,
            "description": self.description,
            "source_url": self.source_url,
        }


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    scholarship_id = Column(Integer, ForeignKey("scholarships.id"), nullable=False, index=True)
    status = Column(
        SAEnum(
            "pending", "in_progress", "submitted", "accepted", "rejected",
            name="application_status_enum",
        ),
        default="pending",
        nullable=False,
    )
    match_score = Column(Float, nullable=True, comment="0.0–1.0 eligibility + relevance score")
    essay = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = relationship("Student", back_populates="applications")
    scholarship = relationship("Scholarship", back_populates="applications")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "student_id": self.student_id,
            "scholarship_id": self.scholarship_id,
            "status": self.status,
            "match_score": self.match_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    type = Column(
        SAEnum("recommendation", "reminder", "update", name="email_type_enum"),
        nullable=False,
    )
    subject = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    status = Column(
        SAEnum("pending", "sent", "failed", name="email_status_enum"),
        default="pending",
        nullable=False,
    )
    error_message = Column(Text, nullable=True)

    student = relationship("Student", back_populates="emails")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "student_id": self.student_id,
            "type": self.type,
            "subject": self.subject,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "status": self.status,
        }
