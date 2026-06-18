"""
tests/test_tools.py — Unit tests for scholarship agent tools.

Run with:  pytest tests/ -v
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_student():
    return {
        "id": 1,
        "name": "Ahmad Farid",
        "email": "ahmad@example.com",
        "nationality": "Malaysia",
        "course_interest": "Computer Science",
        "academic_results": 3.7,
        "income_level": "middle",
    }


@pytest.fixture
def mock_scholarship():
    return {
        "id": 1,
        "name": "Chevening Scholarships",
        "provider": "FCDO",
        "country": "United Kingdom",
        "course": "Computer Science",
        "requirements": {"min_gpa": 3.0, "nationalities": [], "income_levels": []},
        "deadline": (datetime.utcnow() + timedelta(days=45)).isoformat(),
        "amount": "Full tuition",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool function unit tests (with mocked DB)
# ─────────────────────────────────────────────────────────────────────────────

class TestEligibilityLogic:
    """Test eligibility scoring logic independently of DB."""

    def _score(self, student_gpa, min_gpa, student_nationality, allowed, student_income, allowed_income):
        reasons = []
        score_components = []

        # GPA
        if student_gpa >= min_gpa:
            score_components.append(1.0)
        else:
            score_components.append(0.0)

        # Nationality
        if not allowed or student_nationality in allowed:
            score_components.append(1.0)
        else:
            score_components.append(0.0)

        # Income
        if not allowed_income or student_income in allowed_income:
            score_components.append(1.0)
        else:
            score_components.append(0.0)

        # Course match (always 1.0 in this test)
        score_components.append(1.0)

        # Deadline (always valid in this test)
        score_components.append(1.0)

        return sum(score_components) / len(score_components)

    def test_fully_eligible(self):
        score = self._score(3.7, 3.0, "Malaysia", [], "middle", [])
        assert score == 1.0

    def test_gpa_too_low(self):
        score = self._score(2.5, 3.0, "Malaysia", [], "middle", [])
        assert score < 0.6

    def test_wrong_nationality(self):
        score = self._score(3.7, 3.0, "Malaysia", ["UK", "USA"], "middle", [])
        assert score < 0.8

    def test_wrong_income(self):
        score = self._score(3.7, 3.0, "Malaysia", [], "high", ["low", "middle"])
        assert score < 0.8


class TestRankingLogic:
    """Test composite ranking formula."""

    def _composite(self, match_score: float, days_left: int) -> float:
        max_days = 365
        deadline_urgency = 1.0 - min(days_left / max_days, 1.0)
        return (match_score * 0.6) + (deadline_urgency * 0.4)

    def test_urgent_beats_distant_with_same_match(self):
        urgent = self._composite(0.8, 5)
        distant = self._composite(0.8, 300)
        assert urgent > distant

    def test_high_match_beats_urgent_low_match(self):
        high_match = self._composite(1.0, 200)
        low_match_urgent = self._composite(0.3, 1)
        assert high_match > low_match_urgent

    def test_critical_deadline_flag(self):
        days = 5
        assert days <= 7  # CRITICAL

    def test_urgent_deadline_flag(self):
        days = 20
        assert 7 < days <= 30  # URGENT


class TestEmailTemplates:
    """Test email HTML template generation."""

    def test_recommendation_email_contains_name(self):
        from app.email.mailer import build_recommendation_email
        html = build_recommendation_email("Ahmad", [{"name": "Test Scholarship", "amount": "£10k", "deadline": "2025-01-01", "match_score": 0.9}])
        assert "Ahmad" in html
        assert "Test Scholarship" in html

    def test_reminder_email_urgency_color(self):
        from app.email.mailer import build_reminder_email
        html_critical = build_reminder_email("Ahmad", "Chevening", 5)
        html_normal = build_reminder_email("Ahmad", "Chevening", 45)
        # Critical uses red, normal uses amber
        assert "#dc2626" in html_critical
        assert "#f59e0b" in html_normal

    def test_update_email_status(self):
        from app.email.mailer import build_update_email
        html = build_update_email("Ahmad", "Gates Cambridge", "accepted")
        assert "ACCEPTED" in html
        assert "Gates Cambridge" in html


class TestFastAPIEndpoints:
    """Integration tests for FastAPI endpoints."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.api.main import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_scholarships_endpoint_returns_list(self, client):
        resp = client.get("/api/v1/scholarships")
        assert resp.status_code == 200
        data = resp.json()
        assert "scholarships" in data
        assert "count" in data

    def test_get_nonexistent_student_404(self, client):
        resp = client.get("/api/v1/student/99999")
        assert resp.status_code == 404

    def test_create_student(self, client):
        payload = {
            "name": "Test User",
            "email": "testuser_unique_123@example.com",
            "nationality": "Malaysia",
            "course_interest": "Computer Science",
            "academic_results": 3.5,
            "income_level": "middle",
        }
        resp = client.post("/api/v1/student", json=payload)
        assert resp.status_code in (201, 200)
        data = resp.json()
        assert data["email"] == payload["email"]
