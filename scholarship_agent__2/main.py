import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent import run_agent, stream_agent
from config import DATA_DIR, REPORTS_DIR

app = FastAPI(
    title="Scholarship AI Agent",
    description="AI agent that finds, ranks, and reports scholarships for students using the Claude Agent SDK.",
    version="1.0.0",
)


# ── Request / Response models ──────────────────────────────────────────────────

class RunAgentRequest(BaseModel):
    student_id: str | None = None
    prompt: str | None = None


# ── Agent endpoints ────────────────────────────────────────────────────────────

@app.post("/api/agent/run", summary="Run the scholarship agent (blocking)")
async def api_run_agent(req: RunAgentRequest):
    if not req.student_id and not req.prompt:
        raise HTTPException(status_code=400, detail="Provide 'student_id' or 'prompt'.")
    return await run_agent(student_id=req.student_id, custom_prompt=req.prompt)


@app.post("/api/agent/stream", summary="Run the agent and stream events (SSE)")
async def api_stream_agent(req: RunAgentRequest):
    if not req.student_id and not req.prompt:
        raise HTTPException(status_code=400, detail="Provide 'student_id' or 'prompt'.")

    async def event_generator():
        async for event in stream_agent(student_id=req.student_id, custom_prompt=req.prompt):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Data endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/scholarships", summary="List all scholarships in the database")
async def list_scholarships():
    data = json.loads((DATA_DIR / "scholarships.json").read_text(encoding="utf-8"))
    return {"count": len(data), "scholarships": data}


@app.get("/api/scholarships/{scholarship_id}", summary="Get a single scholarship")
async def get_scholarship(scholarship_id: str):
    data = json.loads((DATA_DIR / "scholarships.json").read_text(encoding="utf-8"))
    match = next((s for s in data if s["id"] == scholarship_id), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Scholarship '{scholarship_id}' not found.")
    return match


@app.get("/api/students", summary="List all student profiles")
async def list_students():
    data = json.loads((DATA_DIR / "students.json").read_text(encoding="utf-8"))
    return {"count": len(data), "students": data}


@app.get("/api/students/{student_id}", summary="Get a student profile")
async def get_student(student_id: str):
    data = json.loads((DATA_DIR / "students.json").read_text(encoding="utf-8"))
    student = next((s for s in data if s["id"] == student_id), None)
    if not student:
        raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found.")
    return student


# ── Reports endpoints ──────────────────────────────────────────────────────────

@app.get("/api/reports", summary="List all saved reports")
async def list_reports():
    REPORTS_DIR.mkdir(exist_ok=True)
    files = sorted(REPORTS_DIR.glob("report_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    return {
        "count": len(files),
        "reports": [{"filename": f.name, "size_bytes": f.stat().st_size} for f in files],
    }


@app.get("/api/reports/{filename}", summary="Get a specific report")
async def get_report(filename: str):
    path = REPORTS_DIR / filename
    if not path.exists() or path.suffix != ".json":
        raise HTTPException(status_code=404, detail="Report not found.")
    return json.loads(path.read_text(encoding="utf-8"))


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "agent": "Scholarship AI Agent"}
