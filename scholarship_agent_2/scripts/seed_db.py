"""
scripts/seed_db.py — Populate the database with sample scholarships for testing.

Usage:
    python scripts/seed_db.py
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from app.db.session import SessionLocal, create_tables
from app.db.models import Scholarship

SAMPLE_SCHOLARSHIPS = [
    {
        "name": "Chevening Scholarships",
        "provider": "UK Foreign, Commonwealth & Development Office",
        "country": "United Kingdom",
        "course": "Any postgraduate degree",
        "requirements": {
            "min_gpa": 3.0,
            "nationalities": [],  # open to most countries
            "income_levels": [],  # no income restriction
            "work_experience_years": 2,
        },
        "deadline": datetime.utcnow() + timedelta(days=45),
        "amount": "Full tuition + living allowance",
        "description": (
            "Fully-funded postgraduate scholarships for future leaders. "
            "Covers tuition, accommodation, and return flights."
        ),
        "source_url": "https://www.chevening.org/scholarships/",
    },
    {
        "name": "Gates Cambridge Scholarship",
        "provider": "Bill & Melinda Gates Foundation",
        "country": "United Kingdom",
        "course": "Any degree at University of Cambridge",
        "requirements": {
            "min_gpa": 3.7,
            "nationalities": [],  # international students (non-UK)
            "income_levels": [],
        },
        "deadline": datetime.utcnow() + timedelta(days=20),
        "amount": "Full cost of study + maintenance",
        "description": "Highly competitive scholarship for outstanding students at Cambridge.",
        "source_url": "https://www.gatescambridge.org/",
    },
    {
        "name": "Commonwealth Shared Scholarship",
        "provider": "Commonwealth Scholarship Commission",
        "country": "United Kingdom",
        "course": "STEM and Development-focused postgraduate programs",
        "requirements": {
            "min_gpa": 3.2,
            "nationalities": ["Malaysia", "Nigeria", "Ghana", "Kenya", "India", "Pakistan"],
            "income_levels": ["low", "middle"],
        },
        "deadline": datetime.utcnow() + timedelta(days=60),
        "amount": "Full tuition + living costs + flights",
        "description": "For students from Commonwealth developing countries.",
        "source_url": "https://cscuk.fcdo.gov.uk/scholarships/",
    },
    {
        "name": "DAAD Research Scholarship",
        "provider": "German Academic Exchange Service",
        "country": "Germany",
        "course": "Computer Science, Engineering, Natural Sciences",
        "requirements": {
            "min_gpa": 3.3,
            "nationalities": [],
            "income_levels": [],
        },
        "deadline": datetime.utcnow() + timedelta(days=90),
        "amount": "€934/month + travel allowance",
        "description": "Research scholarships for master's and doctoral candidates in Germany.",
        "source_url": "https://www.daad.de/en/study-and-research-in-germany/scholarships/",
    },
    {
        "name": "Erasmus Mundus Joint Master",
        "provider": "European Commission",
        "country": "European Union",
        "course": "Computer Science, Data Science, AI",
        "requirements": {
            "min_gpa": 3.0,
            "nationalities": [],
            "income_levels": [],
        },
        "deadline": datetime.utcnow() + timedelta(days=30),
        "amount": "€1,400/month + tuition waiver",
        "description": "Joint master's programs across multiple European universities.",
        "source_url": "https://www.eacea.ec.europa.eu/scholarships/emjm",
    },
    {
        "name": "Malaysian Government Scholarship (JPA)",
        "provider": "Public Service Department Malaysia",
        "country": "Malaysia",
        "course": "STEM, Medicine, Law",
        "requirements": {
            "min_gpa": 3.5,
            "nationalities": ["Malaysia"],
            "income_levels": ["low", "middle"],
        },
        "deadline": datetime.utcnow() + timedelta(days=14),
        "amount": "Full tuition + stipend",
        "description": "Federal scholarship for outstanding Malaysian students.",
        "source_url": "https://www.jpa.gov.my/biasiswa",
    },
    {
        "name": "Yayasan Khazanah Scholarship",
        "provider": "Khazanah Nasional",
        "country": "Malaysia",
        "course": "Business, Technology, Economics",
        "requirements": {
            "min_gpa": 3.6,
            "nationalities": ["Malaysia"],
            "income_levels": [],
        },
        "deadline": datetime.utcnow() + timedelta(days=7),
        "amount": "Full tuition + monthly allowance",
        "description": "Prestigious scholarship by Malaysia's sovereign wealth fund.",
        "source_url": "https://www.yayasankhazanah.com.my/",
    },
    {
        "name": "Fulbright Foreign Student Program",
        "provider": "U.S. Department of State",
        "country": "United States",
        "course": "Any graduate field",
        "requirements": {
            "min_gpa": 3.2,
            "nationalities": [],
            "income_levels": [],
        },
        "deadline": datetime.utcnow() + timedelta(days=120),
        "amount": "Full tuition + living stipend + health insurance",
        "description": "US government-funded scholarship for graduate study in the US.",
        "source_url": "https://foreign.fulbrightonline.org/",
    },
    {
        "name": "Google Generation Scholarship",
        "provider": "Google",
        "country": "Any",
        "course": "Computer Science",
        "requirements": {
            "min_gpa": 3.2,
            "nationalities": [],
            "income_levels": [],
        },
        "deadline": datetime.utcnow() + timedelta(days=50),
        "amount": "USD 10,000",
        "description": (
            "For students from underrepresented groups pursuing Computer Science degrees."
        ),
        "source_url": "https://buildyourfuture.withgoogle.com/scholarships",
    },
    {
        "name": "ADB–Japan Scholarship Program",
        "provider": "Asian Development Bank",
        "country": "Asia",
        "course": "Economics, Development, Environment, Science & Technology",
        "requirements": {
            "min_gpa": 3.0,
            "nationalities": ["Malaysia", "Indonesia", "Philippines", "Vietnam", "India"],
            "income_levels": ["low", "middle"],
        },
        "deadline": datetime.utcnow() + timedelta(days=75),
        "amount": "Full cost + travel + health insurance",
        "description": "Postgraduate scholarships for citizens of ADB developing member countries.",
        "source_url": "https://www.adb.org/work-with-us/careers/jsp",
    },
]


def seed():
    create_tables()
    db = SessionLocal()
    try:
        existing = db.query(Scholarship).count()
        if existing > 0:
            print(f"Database already has {existing} scholarships. Skipping seed.")
            return

        for data in SAMPLE_SCHOLARSHIPS:
            scholarship = Scholarship(**data)
            db.add(scholarship)

        db.commit()
        print(f"✅ Seeded {len(SAMPLE_SCHOLARSHIPS)} scholarships successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
