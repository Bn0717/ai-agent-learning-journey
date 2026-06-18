# 🎓 Scholarship Agent

An AI-powered scholarship discovery and application assistant built with the **Claude Agent SDK**. Claude acts as the autonomous orchestrator — deciding which tools to call, in what order, and how to combine results.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI Server                       │
│   POST /chat  │  POST /student  │  GET /scholarships  │ ... │
└───────────────────────────┬─────────────────────────────────┘
                            │
                   ┌────────▼────────┐
                   │  Claude Agent   │  ← claude_agent_sdk
                   │  (Orchestrator) │    reads CLAUDE.md
                   └────────┬────────┘
                            │ decides which tools to call
          ┌─────────────────┼──────────────────────────┐
          │                 │                          │
   ┌──────▼──────┐  ┌───────▼──────┐  ┌───────────────▼──────┐
   │  DB Tools   │  │  Email Tools  │  │   Web Search Tool    │
   │ save_student│  │ send_email_   │  │ search_web_scholar.. │
   │ get_student │  │ notification  │  └──────────────────────┘
   │ search_int..│  └───────────────┘
   │ check_elig. │
   │ rank_schol. │
   │ get_deadlin.│
   │ gen_essay   │
   └──────┬──────┘
          │
   ┌──────▼──────┐
   │  PostgreSQL │
   └─────────────┘
```

**Key principle**: You provide tools. Claude decides when and how to use them. No manual tool-loop code.

---

## Project Structure

```
scholarship_agent/
├── CLAUDE.md                    # Agent behavioral rules (system prompt)
├── app/
│   ├── agent/
│   │   └── runner.py            # Claude Agent SDK orchestrator
│   ├── api/
│   │   └── main.py              # FastAPI endpoints
│   ├── core/
│   │   └── config.py            # Settings (pydantic-settings)
│   ├── db/
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   └── session.py           # DB session factory
│   ├── email/
│   │   └── mailer.py            # SMTP/SendGrid + HTML templates
│   └── tools/
│       └── scholarship_tools.py # All 9 Agent SDK tools
├── scripts/
│   ├── seed_db.py               # Populate sample scholarships
│   └── send_reminders.py        # Deadline reminder cron job
├── tests/
│   └── test_tools.py            # Unit + integration tests
├── alembic/
│   └── env.py                   # DB migration config
├── docker/
│   └── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Quick Start

### Option A — Docker (recommended)

```bash
# 1. Clone and enter project
git clone <your-repo> && cd scholarship_agent

# 2. Set up environment
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY at minimum

# 3. Start everything
docker-compose up --build

# 4. API is live at http://localhost:8000
# 5. Docs at http://localhost:8000/docs
```

### Option B — Local Development

```bash
# Prerequisites: Python 3.11+, PostgreSQL 14+

# 1. Create virtual environment
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY and DATABASE_URL

# 4. Create database
createdb scholarship_db

# 5. Seed sample scholarships
python scripts/seed_db.py

# 6. Start the server
uvicorn app.api.main:app --reload --port 8000
```

---

## API Reference

### Chat with the Agent

```bash
# Single-turn
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Find scholarships for Computer Science in the UK. My email is ahmad@example.com"}'

# With session (multi-turn)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Generate an essay for the top scholarship", "session_id": "my-session-123"}'

# Streaming (SSE)
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What scholarships am I eligible for?"}'
```

### Student Management

```bash
# Create student profile
curl -X POST http://localhost:8000/api/v1/student \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ahmad Farid",
    "email": "ahmad@example.com",
    "nationality": "Malaysia",
    "course_interest": "Computer Science",
    "academic_results": 3.7,
    "income_level": "middle"
  }'

# Get student profile
curl http://localhost:8000/api/v1/student/1
```

### Scholarships

```bash
# List all scholarships
curl "http://localhost:8000/api/v1/scholarships"

# Filter by country and course
curl "http://localhost:8000/api/v1/scholarships?country=UK&course=Computer+Science"

# Add a scholarship (admin)
curl -X POST http://localhost:8000/api/v1/scholarships \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Scholarship",
    "provider": "Acme Corp",
    "country": "USA",
    "course": "Engineering",
    "requirements": {"min_gpa": 3.5},
    "deadline": "2025-12-31T23:59:00",
    "amount": "$5,000"
  }'
```

### Send Email

```bash
curl -X POST http://localhost:8000/api/v1/email/send \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": 1,
    "email_type": "recommendation",
    "scholarships": [{"name": "Chevening", "amount": "Full tuition", "deadline": "2025-10-01", "match_score": 0.92}]
  }'
```

---

## Agent Workflow

When you send `"Find scholarships for Computer Science in the UK"`:

1. **`get_student_profile`** — load or request profile  
2. **`search_internal_scholarships`** — query DB (`country=UK, course=Computer Science`)  
3. **`search_web_scholarships`** — supplement if fewer than 3 internal matches  
4. **`check_eligibility`** — run eligibility check for each candidate  
5. **`rank_scholarships`** — sort by `(match × 0.6) + (urgency × 0.4)`  
6. Explain recommendations clearly with urgency flags  
7. Offer **`send_email_notification`** for an emailed summary  

---

## Database Schema

| Table | Key Columns |
|-------|-------------|
| `students` | id, name, email, nationality, course_interest, academic_results, income_level |
| `scholarships` | id, name, provider, country, course, requirements (JSON), deadline, amount |
| `applications` | id, student_id, scholarship_id, status, match_score, essay |
| `emails` | id, student_id, type, subject, content, sent_at, status |

---

## Email Configuration

**SMTP (Gmail)**:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your_app_password   # Use Gmail App Password, not account password
```

**SendGrid** (priority when set):
```env
SENDGRID_API_KEY=SG.xxxx
```

---

## Deadline Reminders (Cron)

```bash
# Run manually
python scripts/send_reminders.py

# Schedule daily at 9am (crontab)
0 9 * * * cd /app && python scripts/send_reminders.py >> /var/log/reminders.log 2>&1
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Your Anthropic API key |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `SMTP_USER` / `SMTP_PASSWORD` | ⚠️ | Required for email via Gmail |
| `SENDGRID_API_KEY` | Optional | Takes priority over SMTP |
| `SERPER_API_KEY` | Optional | Enables web scholarship search |
| `REDIS_URL` | Optional | Enables response caching |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| AI Orchestrator | Claude Agent SDK (`claude-agent-sdk`) |
| Web Framework | FastAPI |
| Database | PostgreSQL + SQLAlchemy |
| Email | SMTP / SendGrid |
| Migrations | Alembic |
| Container | Docker + Docker Compose |
| Testing | pytest + FastAPI TestClient |
