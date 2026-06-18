import base64
import tempfile
import traceback
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent import run_agent

app = FastAPI(
    title="Scholarship Agent API",
    description="AI-powered scholarship finder using Claude Code Agent SDK on Vertex AI",
    version="1.0.0",
)


class RunRequest(BaseModel):
    resume_base64: str       # base64-encoded PDF content
    recipient_email: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/agent/run")
async def run(req: RunRequest):
    try:
        pdf_bytes = base64.b64decode(req.resume_base64)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir="/tmp") as f:
            f.write(pdf_bytes)
            resume_path = f.name
        result = await run_agent(resume_path, req.recipient_email)
        Path(resume_path).unlink(missing_ok=True)
        return {
            "status": "completed",
            "recipient_email": req.recipient_email,
            "result": result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
