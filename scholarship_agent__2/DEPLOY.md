# Deploying Scholarship Agent to Google Cloud Run

## Prerequisites

1. **Google Cloud Project** — `brain-433706` (already set up)
2. **Google Cloud CLI** — Install from https://cloud.google.com/sdk/docs/install
3. **Docker** — Install from https://www.docker.com/products/docker-desktop
4. **gcloud configured** — Run `gcloud auth login`

---

## Step 1: Prepare Environment Variables

Create a `.env.prod` file with your production credentials:

```env
GOOGLE_CLOUD_PROJECT=brain-433706
GOOGLE_CLOUD_LOCATION=asia-southeast1
CLAUDE_CODE_USE_VERTEX=1

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
```

**Note**: Cloud Run doesn't use `.env` files directly. You'll set these as **Secrets** or **Environment Variables** in the Cloud Run console.

---

## Step 2: Create Cloud Storage Bucket (for data files)

The app needs access to `data/students.json` and `data/scholarships.json`. Options:

### Option A: Include data in Docker image (simpler for demo)
Files are already in `data/` folder — they'll be copied into the container.

### Option B: Load from Cloud Storage (production)
```bash
gsutil mb gs://scholarship-agent-data-brain/
gsutil cp data/*.json gs://scholarship-agent-data-brain/
```
Then update code to load from GCS instead of local files.

**We'll use Option A for now (simpler).**

---

## Step 3: Deploy to Cloud Run

### Option 1: Deploy from Source (Recommended)

```bash
gcloud run deploy scholarship-agent \
  --source . \
  --region asia-southeast1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=brain-433706,GOOGLE_CLOUD_LOCATION=asia-southeast1,CLAUDE_CODE_USE_VERTEX=1
```

### Option 2: Build & Deploy Manually

```bash
# Build Docker image
docker build -t scholarship-agent:latest .

# Tag for Google Cloud
docker tag scholarship-agent:latest gcr.io/brain-433706/scholarship-agent:latest

# Push to Container Registry
docker push gcr.io/brain-433706/scholarship-agent:latest

# Deploy from image
gcloud run deploy scholarship-agent \
  --image gcr.io/brain-433706/scholarship-agent:latest \
  --region asia-southeast1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=brain-433706,GOOGLE_CLOUD_LOCATION=asia-southeast1,CLAUDE_CODE_USE_VERTEX=1
```

---

## Step 4: Set Cloud Run Configuration

After deployment, go to Google Cloud Console and add **Secret Variables**:

1. Go to: `Cloud Run` → `scholarship-agent` → `Edit & Deploy`
2. Click **"Set up Cloud Secret Manager"**
3. Add secrets:
   - `SMTP_PASSWORD` (reference secret in Cloud Secret Manager)
   - `SMTP_USER`
   - `EMAIL_FROM`

---

## Step 5: Test the Deployment

Get the Cloud Run service URL:

```bash
gcloud run services describe scholarship-agent --region asia-southeast1 --format 'value(status.url)'
```

Then test the API:

```bash
# Run agent for student S001
curl -X POST https://scholarship-agent-xxxxx.run.app/api/agent/run \
  -H "Content-Type: application/json" \
  -d '{"student_id": "S001"}'

# Stream results (Server-Sent Events)
curl -X POST https://scholarship-agent-xxxxx.run.app/api/agent/stream \
  -H "Content-Type: application/json" \
  -d '{"student_id": "S001"}'

# Get list of available students
curl https://scholarship-agent-xxxxx.run.app/api/students

# Get list of reports
curl https://scholarship-agent-xxxxx.run.app/api/reports
```

---

## Step 6: Monitor & Logs

View real-time logs:

```bash
gcloud run logs read scholarship-agent --region asia-southeast1 --limit 50 --follow
```

View in Cloud Console:
- Go to `Cloud Run` → `scholarship-agent` → `Logs`

---

## Troubleshooting

### "Permission denied" error
```bash
gcloud auth application-default login
gcloud config set project brain-433706
```

### Container fails to start
Check logs:
```bash
gcloud run logs read scholarship-agent --region asia-southeast1 --limit 100
```

### Port issues
Cloud Run automatically assigns PORT. The Dockerfile uses `${PORT}` env var (default 8080).

### Out of memory
If agent times out:
- Go to Cloud Run console → `scholarship-agent` → `Edit & Deploy`
- Increase **Memory** (default 256 MB, try 512 MB or 1 GB)
- Increase **Timeout** (default 300s, try 600s)

---

## Cost Estimation

**Cloud Run Pricing** (as of 2024):
- **Compute**: $0.00001667/vCPU-second (128 MB instance ≈ 0.125 vCPU)
- **Request**: $0.40 per 1M requests
- **Vertex AI Claude**: $3–$15 per 1M tokens (via SDK)

**Example**: 100 agent runs/month
- Cloud Run: ~$0.50–$2.00/month
- Vertex AI tokens: ~$0.50–$5.00/month (depending on scholarship database size)

---

## Next Steps

1. **Run deployment command** (Step 3, Option 1)
2. **Test endpoints** (Step 5)
3. **Monitor logs** (Step 6)
4. **Share service URL** with users

---

## Quick Start (Copy-Paste)

```bash
# Set project
gcloud config set project brain-433706

# Deploy (from source directory)
gcloud run deploy scholarship-agent \
  --source . \
  --region asia-southeast1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=brain-433706,GOOGLE_CLOUD_LOCATION=asia-southeast1,CLAUDE_CODE_USE_VERTEX=1

# Get service URL
gcloud run services describe scholarship-agent --region asia-southeast1 --format 'value(status.url)'
```

That's it! Your agent will be live.
