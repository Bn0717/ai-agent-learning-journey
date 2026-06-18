import sqlite3
import pathlib

DB_PATH = pathlib.Path('scholarship.db')


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY,
        name TEXT,
        nationality TEXT,
        degree_level TEXT,
        field_of_study TEXT,
        cgpa REAL,
        email TEXT,
        financial_need INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS internal_scholarships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        provider TEXT,
        coverage TEXT,
        eligibility TEXT,
        deadline TEXT,
        application_link TEXT,
        field_of_study TEXT,
        nationality TEXT,
        degree_level TEXT,
        min_cgpa REAL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS tracked_scholarships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        scholarship_name TEXT,
        provider TEXT,
        deadline TEXT,
        application_link TEXT,
        status TEXT DEFAULT 'interested',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    c.executemany("INSERT OR IGNORE INTO students VALUES (?,?,?,?,?,?,?,?)", [
        ("STU001", "Ahmad Farid", "Malaysian", "undergraduate", "Computer Science", 3.8, "ahmad@example.com", 1),
        ("STU002", "Li Wei",      "Malaysian", "postgraduate",  "Engineering",       3.5, "liwei@example.com",  0),
    ])
    c.executemany(
        "INSERT OR IGNORE INTO internal_scholarships (name,provider,coverage,eligibility,deadline,application_link,field_of_study,nationality,degree_level,min_cgpa) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("Sunway Excellence Award", "Sunway Group", "Full tuition",  "CGPA 3.5+, Malaysian", "2026-07-31", "https://sunway.edu.my/scholarships", "any", "Malaysian", "undergraduate", 3.5),
            ("CIMB ASEAN Scholarship",  "CIMB Bank",    "RM 36,000/yr", "CGPA 3.7+, ASEAN",     "2026-06-30", "https://cimb.com/scholarship",        "any", "any",       "undergraduate", 3.7),
        ]
    )
    conn.commit()
    conn.close()


def get_student_profile(student_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    conn.close()
    return dict(row) if row else {"error": f"Student '{student_id}' not found"}


def search_internal_scholarships(field_of_study: str = None, nationality: str = None, degree_level: str = None) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    q, params = "SELECT * FROM internal_scholarships WHERE 1=1", []
    if field_of_study:
        q += " AND (field_of_study LIKE ? OR field_of_study = 'any')"
        params.append(f"%{field_of_study}%")
    if nationality:
        q += " AND (nationality LIKE ? OR nationality = 'any')"
        params.append(f"%{nationality}%")
    if degree_level:
        q += " AND (degree_level LIKE ? OR degree_level = 'any')"
        params.append(f"%{degree_level}%")
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
