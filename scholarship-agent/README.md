# Scholarship Agent

AI-powered scholarship research agent. Given a query, it searches for real open scholarships and emails a formatted report.

## Local run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Then test:

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "Computer Science scholarships for Malaysians"}'
```

## Deploy to Cloud Run

```bash
gcloud config set project brain

gcloud builds submit --tag gcr.io/brain/scholarship-agent

gcloud run deploy scholarship-agent \
  --image gcr.io/brain/scholarship-agent \
  --platform managed \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_key,GMAIL_USER=your@gmail.com,GMAIL_APP_PASSWORD=yourpass,RECIPIENT_EMAIL=your@gmail.com
```

## Test deployed endpoint

```bash
curl -X POST https://your-cloud-run-url/research \
  -H "Content-Type: application/json" \
  -d '{"query": "Computer Science scholarships for Malaysians"}'
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/research` | Run scholarship research |

## Environment variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key |
| `GMAIL_USER` | Gmail address to send from |
| `GMAIL_APP_PASSWORD` | Gmail App Password (16-char) |
| `RECIPIENT_EMAIL` | Email address to receive reports |
