# -*- coding: utf-8 -*-
"""
Bootstrap the SQLite database with schema and fake data.
Run once:  python setup_db.py
The agent also calls this automatically on first run.
"""

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from faker import Faker

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///scholarship.db")
DB_PATH = DATABASE_URL.replace("sqlite:///", "")

fake = Faker()

STUDENTS = [
    # Target student always first
    {
        "name": "Alex Tan",
        "email": "sunwaypropertyit@sunway.com.my",
        "gpa": 3.7,
        "field_of_study": "Computer Science",
        "nationality": "Malaysian",
        "year_level": "Sophomore",
        "interests": "AI, machine learning, data science",
        "background": "Sunway University, active in coding clubs and hackathons",
    },
]

FIELDS = ["Computer Science", "Engineering", "Biology", "Business", "Mathematics", "Physics", "Data Science"]
NATIONALITIES = ["Malaysian", "Indonesian", "Thai", "Vietnamese", "Singaporean", "Filipino", "Chinese", "Indian"]

for _ in range(14):
    STUDENTS.append({
        "name": fake.name(),
        "email": fake.unique.email(),
        "gpa": round(fake.pyfloat(min_value=2.5, max_value=4.0, right_digits=1), 1),
        "field_of_study": fake.random_element(FIELDS),
        "nationality": fake.random_element(NATIONALITIES),
        "year_level": fake.random_element(["Freshman", "Sophomore", "Junior", "Senior"]),
        "interests": ", ".join(fake.words(nb=3)),
        "background": fake.sentence(),
    })

SCHOLARSHIPS = [
    {
        "name": "Google APAC Scholarship",
        "amount": 10000,
        "currency": "USD",
        "eligibility": "STEM students in Asia Pacific with GPA >= 3.5",
        "min_gpa": 3.5,
        "field": "Computer Science",
        "nationality": "ANY",
        "deadline": "2026-09-30",
        "link": "https://buildyourfuture.withgoogle.com/scholarships",
        "description": "Merit-based scholarship for APAC STEM students.",
    },
    {
        "name": "Khazanah Global Scholarship",
        "amount": 50000,
        "currency": "MYR",
        "eligibility": "Malaysian students pursuing postgraduate studies",
        "min_gpa": 3.5,
        "field": "ANY",
        "nationality": "Malaysian",
        "deadline": "2026-07-31",
        "link": "https://www.khazanah.com.my/sustainability/khazanah-scholarships/",
        "description": "Fully-funded scholarship for top Malaysian graduates.",
    },
    {
        "name": "Yayasan Tenaga Nasional Scholarship",
        "amount": 30000,
        "currency": "MYR",
        "eligibility": "Malaysian students in engineering or technology",
        "min_gpa": 3.3,
        "field": "Engineering",
        "nationality": "Malaysian",
        "deadline": "2026-08-15",
        "link": "https://www.ytn.com.my",
        "description": "TNB scholarship for Malaysian engineering students.",
    },
    {
        "name": "ASEAN Data Science Explorers",
        "amount": 5000,
        "currency": "USD",
        "eligibility": "ASEAN students with interest in data and AI",
        "min_gpa": 3.0,
        "field": "Data Science",
        "nationality": "ANY",
        "deadline": "2026-10-01",
        "link": "https://www.sap.com/sea/about/asean-scholarship.html",
        "description": "SAP-sponsored scholarship for ASEAN data science students.",
    },
    {
        "name": "Microsoft Research Asia Fellowship",
        "amount": 8000,
        "currency": "USD",
        "eligibility": "Outstanding students in CS or related fields",
        "min_gpa": 3.5,
        "field": "Computer Science",
        "nationality": "ANY",
        "deadline": "2026-11-30",
        "link": "https://www.microsoft.com/en-us/research/academic-program/fellowships/",
        "description": "Fellowship for research-oriented CS students in Asia.",
    },
    {
        "name": "Bank Negara Malaysia Scholarship",
        "amount": 40000,
        "currency": "MYR",
        "eligibility": "Malaysian students in economics, finance, or IT",
        "min_gpa": 3.5,
        "field": "Computer Science",
        "nationality": "Malaysian",
        "deadline": "2026-06-30",
        "link": "https://www.bnm.gov.my/scholarship",
        "description": "Scholarship from Malaysia's central bank.",
    },
    {
        "name": "Petronas Education Sponsorship",
        "amount": 35000,
        "currency": "MYR",
        "eligibility": "Malaysian STEM undergraduates with strong academics",
        "min_gpa": 3.3,
        "field": "Engineering",
        "nationality": "Malaysian",
        "deadline": "2026-07-15",
        "link": "https://www.petronas.com/sustainability/people/scholarships",
        "description": "PETRONAS sponsorship for high-achieving Malaysian students.",
    },
    {
        "name": "AWS Machine Learning Scholarship",
        "amount": 4000,
        "currency": "USD",
        "eligibility": "Students with demonstrated interest in ML/AI",
        "min_gpa": 3.0,
        "field": "Computer Science",
        "nationality": "ANY",
        "deadline": "2026-12-01",
        "link": "https://aws.amazon.com/machine-learning/scholarship/",
        "description": "AWS scholarship for students pursuing ML education.",
    },
    {
        "name": "NVIDIA Graduate Fellowship",
        "amount": 15000,
        "currency": "USD",
        "eligibility": "Graduate students in GPU computing, AI, or graphics",
        "min_gpa": 3.5,
        "field": "Computer Science",
        "nationality": "ANY",
        "deadline": "2026-09-15",
        "link": "https://research.nvidia.com/graduate-fellowships",
        "description": "NVIDIA fellowship for AI and GPU research.",
    },
    {
        "name": "Sunway Education Group Scholarship",
        "amount": 20000,
        "currency": "MYR",
        "eligibility": "Students at Sunway University with high academic achievement",
        "min_gpa": 3.5,
        "field": "ANY",
        "nationality": "ANY",
        "deadline": "2026-08-31",
        "link": "https://university.sunway.edu.my/scholarships",
        "description": "Merit scholarship for Sunway University students.",
    },
    {
        "name": "STEM Women Scholarship",
        "amount": 6000,
        "currency": "USD",
        "eligibility": "Women pursuing STEM degrees",
        "min_gpa": 3.0,
        "field": "ANY",
        "nationality": "ANY",
        "deadline": "2026-10-31",
        "link": "https://www.stemwomen.com/scholarship",
        "description": "Scholarship supporting women in STEM fields.",
    },
    {
        "name": "Erasmus Mundus Joint Master Scholarship",
        "amount": 25000,
        "currency": "EUR",
        "eligibility": "International students for joint master programmes in Europe",
        "min_gpa": 3.3,
        "field": "ANY",
        "nationality": "ANY",
        "deadline": "2027-01-15",
        "link": "https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters-scholarships",
        "description": "EU-funded scholarship for international master's students.",
    },
    {
        "name": "Huawei Seeds for the Future",
        "amount": 3000,
        "currency": "USD",
        "eligibility": "Top ICT students in ASEAN",
        "min_gpa": 3.2,
        "field": "Computer Science",
        "nationality": "ANY",
        "deadline": "2026-08-01",
        "link": "https://www.huawei.com/en/seeds-for-the-future",
        "description": "Huawei programme for outstanding ICT talent in ASEAN.",
    },
    {
        "name": "JPA Public Service Scholarship",
        "amount": 45000,
        "currency": "MYR",
        "eligibility": "Top Malaysian students for overseas undergraduate studies",
        "min_gpa": 3.8,
        "field": "ANY",
        "nationality": "Malaysian",
        "deadline": "2026-06-15",
        "link": "https://www.jpa.gov.my/en/scholarship",
        "description": "Malaysian government scholarship for top students.",
    },
    {
        "name": "MARA Scholarship",
        "amount": 40000,
        "currency": "MYR",
        "eligibility": "Bumiputera Malaysian students with excellent results",
        "min_gpa": 3.5,
        "field": "ANY",
        "nationality": "Malaysian",
        "deadline": "2026-07-01",
        "link": "https://www.mara.gov.my/en/scholarship",
        "description": "MARA scholarship for Bumiputera undergraduates.",
    },
    {
        "name": "Intel AI Student Innovator Award",
        "amount": 5000,
        "currency": "USD",
        "eligibility": "Students building AI/ML projects",
        "min_gpa": 3.0,
        "field": "Computer Science",
        "nationality": "ANY",
        "deadline": "2026-11-01",
        "link": "https://www.intel.com/content/www/us/en/research/students.html",
        "description": "Award for students creating innovative AI solutions.",
    },
    {
        "name": "CIMB ASEAN Scholarship",
        "amount": 15000,
        "currency": "MYR",
        "eligibility": "ASEAN students in business, technology, or finance",
        "min_gpa": 3.3,
        "field": "Computer Science",
        "nationality": "ANY",
        "deadline": "2026-09-01",
        "link": "https://www.cimb.com/en/who-we-are/cimb-foundation/scholarships.html",
        "description": "CIMB Foundation scholarship for ASEAN talent.",
    },
    {
        "name": "Maybank Scholarship",
        "amount": 25000,
        "currency": "MYR",
        "eligibility": "Malaysian students in finance, IT, or related fields",
        "min_gpa": 3.5,
        "field": "Computer Science",
        "nationality": "Malaysian",
        "deadline": "2026-08-30",
        "link": "https://www.maybank.com/en/about-us/corporate-responsibility/education/scholarship.page",
        "description": "Maybank scholarship for high-performing Malaysian students.",
    },
    {
        "name": "Alibaba Cloud Global Scholarship",
        "amount": 6000,
        "currency": "USD",
        "eligibility": "Students with cloud computing or AI interests",
        "min_gpa": 3.0,
        "field": "Computer Science",
        "nationality": "ANY",
        "deadline": "2026-10-15",
        "link": "https://edu.alibabacloud.com/scholarship",
        "description": "Alibaba Cloud scholarship for aspiring cloud engineers.",
    },
    {
        "name": "Commonwealth Scholarship",
        "amount": 30000,
        "currency": "GBP",
        "eligibility": "Commonwealth country students for UK postgraduate study",
        "min_gpa": 3.5,
        "field": "ANY",
        "nationality": "Malaysian",
        "deadline": "2026-12-15",
        "link": "https://cscuk.fcdo.gov.uk/scholarships/commonwealth-scholarships/",
        "description": "UK government scholarship for Commonwealth students.",
    },
]


def setup():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
        DROP TABLE IF EXISTS applications;
        DROP TABLE IF EXISTS scholarships;
        DROP TABLE IF EXISTS students;

        CREATE TABLE IF NOT EXISTS students (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            gpa         REAL,
            field_of_study TEXT,
            nationality TEXT,
            year_level  TEXT,
            interests   TEXT,
            background  TEXT
        );

        CREATE TABLE IF NOT EXISTS scholarships (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            amount      REAL,
            currency    TEXT,
            eligibility TEXT,
            min_gpa     REAL,
            field       TEXT,
            nationality TEXT,
            deadline    TEXT,
            link        TEXT,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS applications (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            student_email   TEXT NOT NULL,
            scholarship_name TEXT NOT NULL,
            rank            INTEGER,
            match_score     REAL,
            reason          TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            UNIQUE(student_email, scholarship_name)
        );
    """)

    for s in STUDENTS:
        cur.execute("""
            INSERT OR IGNORE INTO students
                (name, email, gpa, field_of_study, nationality, year_level, interests, background)
            VALUES (:name, :email, :gpa, :field_of_study, :nationality, :year_level, :interests, :background)
        """, s)

    for s in SCHOLARSHIPS:
        cur.execute("""
            INSERT OR IGNORE INTO scholarships
                (name, amount, currency, eligibility, min_gpa, field, nationality, deadline, link, description)
            VALUES (:name, :amount, :currency, :eligibility, :min_gpa, :field, :nationality, :deadline, :link, :description)
        """, s)

    conn.commit()
    conn.close()
    print(f"Database ready: {DB_PATH}")
    print(f"  {len(STUDENTS)} students, {len(SCHOLARSHIPS)} scholarships seeded.")


if __name__ == "__main__":
    setup()
