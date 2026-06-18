# 🎓 Scholarship Agent

Built with **Claude Code Agent SDK (Python)** + **Google Vertex AI** + **FastAPI**.
Matches your whiteboard: Vertex → Claude SDK → Agent → FastAPI ← NextAPI.

---

## Project structure

```
scholarship-agent/
├── agent.py                          ← Agent loop + FastAPI endpoints
├── CLAUDE.md                         ← Skill names + descriptions (LLM reads this)
├── README.md
└── skills/
    ├── __init__.py
    ├── web_search_scholarships.py    ← Skill 1: search web
    ├── save_to_database.py           ← Skill 2: SQLite DB
    └── send_scholarship_email.py     ← Skill 3: Gmail SMTP
```

---

## How skills work

```
CLAUDE.md defines:          skills/*.py implements:
  name: web_search_scholarships  →  def web_search_scholarships(...)
  description: "search web..."   →  actual Python logic

LLM reads the name + description in CLAUDE.md
→ decides which skill to call
→ agent.py executes the matching .py function
```

---

## Setup

```bash
pip install claude-agent-sdk fastapi uvicorn

# Google Vertex AI (no API key needed on Cloud Run)
export CLAUDE_CODE_USE_VERTEX=1
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=asia-southeast1

# Email
export EMAIL_SENDER=you@gmail.com
export EMAIL_PASSWORD=your-app-password
```

---

## Run

```bash
# As a script
python agent.py

# As FastAPI (for Cloud Run / NextJS frontend)
uvicorn agent:app --reload

# Endpoints:
POST http://localhost:8000/find-scholarships   ← trigger full agent
GET  http://localhost:8000/scholarships/{email} ← query saved results
```

---

## POST body example

```json
{
  "name": "Alex Tan",
  "email": "alex@example.com",
  "field": "Computer Science",
  "gpa": "3.7",
  "nationality": "Malaysian",
  "year": "Undergraduate sophomore",
  "background": "First-generation college student, financial need"
}
```
