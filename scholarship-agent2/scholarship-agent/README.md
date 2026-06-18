# 🎓 Scholarship Agent

AI-powered scholarship finder built with the **Claude Code Agent SDK** on **Google Vertex AI**.
Exposed as a **FastAPI REST API** and deployed on **Google Cloud Run**.

---

## Architecture

```
POST /agent/run
      │
      ▼
  FastAPI (main.py)
      │
      ▼
  Claude Agent (claude-sonnet-4-6 on Vertex AI)
      │  reads skills from .claude/skills/
      │  uses WebSearch, WebFetch, Bash tools autonomously
      │
      ├── queries PostgreSQL for student profile & scholarships
      ├── searches the web for additional open scholarships
      ├── ranks & generates a personalised report
      ├── saves recommendations to PostgreSQL
      └── emails the student via Gmail SMTP
```

---

## Project Structure

```
scholarship-agent/
├── main.py                               ← FastAPI app
├── agent.py                              ← agent entry point (also runnable directly)
├── Dockerfile                            ← container for Cloud Run
├── requirements.txt
├── .env.example                          ← copy to .env and fill in values
├── CLAUDE.md                             ← agent persona + available skills
└── .claude/
    └── skills/
        ├── get-student-profile/SKILL.md
        ├── search-scholarships/SKILL.md
        ├── rank-summarize/SKILL.md
        ├── generate-report/SKILL.md
        ├── database/SKILL.md
        ├── send-email/SKILL.md
        └── summarize/SKILL.md
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in all values before running.

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (see below) |
| `CLAUDE_CODE_USE_VERTEX` | Set to `1` to use Google Vertex AI |
| `GOOGLE_CLOUD_PROJECT` | Your GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | Vertex AI region, e.g. `asia-southeast1` |
| `EMAIL_SENDER` | Gmail address used to send reports |
| `EMAIL_PASSWORD` | Gmail App Password (not your account password) |

---

## 1. Get a PostgreSQL Database URL

The `DATABASE_URL` format is:
```
postgresql://USERNAME:PASSWORD@HOST:PORT/DATABASE_NAME
```

### Option A — Supabase (recommended for quick start, free tier)

1. Go to [supabase.com](https://supabase.com) and create a free account.
2. Click **New Project**, choose a name and a strong password, select a region close to your Cloud Run region.
3. Wait for the project to finish provisioning (~2 minutes).
4. Go to **Project Settings → Database → Connection string → URI**.
5. Copy the URI — it looks like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```
6. Replace `[YOUR-PASSWORD]` with the password you set in step 2.

### Option B — Cloud SQL (recommended for production on GCP)

1. In the [GCP Console](https://console.cloud.google.com), go to **SQL → Create Instance → PostgreSQL**.
2. Choose a name (e.g. `scholarship-db`), set a root password, pick a region matching your Cloud Run region.
3. After creation, go to **Databases** and create a database named `scholarships`.
4. Go to **Users** and create a user (e.g. `agent` with a password).
5. For Cloud Run, use the **Cloud SQL Auth Proxy** connection format:
   ```
   postgresql://agent:PASSWORD@localhost/scholarships?host=/cloudsql/PROJECT:REGION:INSTANCE
   ```
   Set `INSTANCE_CONNECTION_NAME` as an env var and mount the socket in Cloud Run (see Cloud Run docs for Cloud SQL connections).

### Option C — Local PostgreSQL (for development)

If you have PostgreSQL installed locally:
```bash
createdb scholarships
```
Then set:
```
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/scholarships
```

---

## 2. Get a Gmail App Password

1. Go to your Google Account → [Security](https://myaccount.google.com/security).
2. Enable **2-Step Verification** if not already on.
3. Search for **App passwords** and click it.
4. Select app: **Mail**, device: **Other** → type `ScholarshipAgent` → click **Generate**.
5. Copy the 16-character password — this is your `EMAIL_PASSWORD`.

---

## 3. Google Vertex AI Setup

The agent uses `claude-sonnet-4-6` via Vertex AI — no Anthropic API key needed.

```bash
# Install Google Cloud CLI
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable aiplatform.googleapis.com run.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com
```

---

## 4. Run Locally

### With Docker (recommended)

```bash
cp .env.example .env
# Edit .env with your values

docker build -t scholarship-agent .
docker run --env-file .env -p 8080:8080 scholarship-agent
```

### Without Docker

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values

uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

API is available at `http://localhost:8080`.
Interactive docs at `http://localhost:8080/docs`.

---

## 5. API Endpoints

### Health check
```http
GET /health
```
```json
{ "status": "ok" }
```

### Run the scholarship agent
```http
POST /agent/run
Content-Type: application/json

{ "student_email": "sunwaypropertyit@sunway.com.my" }
```
```json
{
  "status": "completed",
  "student_email": "sunwaypropertyit@sunway.com.my",
  "result": "Here's a summary of your scholarship search, Alex..."
}
```

> **Note:** This endpoint runs the full agent pipeline (search, rank, save, email). It may take 1–3 minutes. Set your client timeout accordingly. On Cloud Run, set `--timeout=3600`.

---

## 6. Deploy to Google Cloud Run

```bash
# Set your project
export PROJECT_ID=your-gcp-project-id
export REGION=asia-southeast1
export IMAGE=gcr.io/$PROJECT_ID/scholarship-agent

# Build and push
gcloud builds submit --tag $IMAGE

# Deploy to Cloud Run
gcloud run deploy scholarship-agent \
  --image $IMAGE \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --timeout=3600 \
  --memory=1Gi \
  --set-env-vars="CLAUDE_CODE_USE_VERTEX=1" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
  --set-env-vars="GOOGLE_CLOUD_LOCATION=$REGION" \
  --set-env-vars="DATABASE_URL=your-database-url" \
  --set-env-vars="EMAIL_SENDER=you@gmail.com" \
  --set-env-vars="EMAIL_PASSWORD=your-app-password"
```

After deployment, Cloud Run prints the service URL. Test it:
```bash
curl -X POST https://YOUR-SERVICE-URL/agent/run \
  -H "Content-Type: application/json" \
  -d '{"student_email": "sunwaypropertyit@sunway.com.my"}'
```

---

## 7. Run the Agent Directly (CLI)

```bash
python agent.py
```

This bypasses FastAPI and runs the agent directly for the default `STUDENT_EMAIL` in `agent.py`.
