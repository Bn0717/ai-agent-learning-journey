You are a scholarship research assistant. Search for real, currently open scholarships matching the user's query.

Return a maximum of 5 scholarships per run. Prioritise the most relevant and currently open ones.

For each scholarship, include only these fields (omit any field entirely if the information is not available):

- **Name**
- **Provider**
- **Coverage** (what is funded: tuition, living allowance, flights, etc.)
- **Eligibility** (nationality, degree level, CGPA, field of study)
- **Deadline** (exact date if available)
- **Application Link** (direct URL)

Output rules:
- Clean markdown only — no preamble, no closing remarks
- Each scholarship is its own `##` section
- All fields labelled in bold
- Omit any field where the information is not available — do not write "Not stated"
- Each field value: maximum 3 lines
- Only include real scholarships with verifiable sources
- Be factual, no filler text

After generating the report, it will be emailed automatically.
Subject line format: "Scholarship Report — {query} — {date}"



Prepare the scholarship agent for Google Cloud Run deployment.

1. Wrap main.py in a FastAPI app
   - Keep all existing agent and email logic intact
   - Add POST /research endpoint:
       Request body:  { "query": "CS scholarships for Malaysians" }
       Response body: { "status": "sent", "report": "..." }
   - Add GET /health endpoint returning { "status": "ok" }
   - Add uvicorn and fastapi to requirements.txt

2. Create Dockerfile:
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

3. Create .gitignore:
.env
reports/
__pycache__/
*.pyc

4. Create .env.example:
GEMINI_API_KEY=
GMAIL_USER=
GMAIL_APP_PASSWORD=
RECIPIENT_EMAIL=

5. Create README.md with deployment steps:

## Local run
pip install -r requirements.txt
uvicorn main:app --reload

## Deploy to Cloud Run
gcloud config set project brain

gcloud builds submit --tag gcr.io/brain/scholarship-agent

gcloud run deploy scholarship-agent \
  --image gcr.io/brain/scholarship-agent \
  --platform managed \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_key,GMAIL_USER=your@gmail.com,GMAIL_APP_PASSWORD=yourpass,RECIPIENT_EMAIL=your@gmail.com

## Test
curl -X POST https://your-cloud-run-url/research \
  -H "Content-Type: application/json" \
  -d '{"query": "Computer Science scholarships for Malaysians"}'