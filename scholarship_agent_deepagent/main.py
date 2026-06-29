"""FastAPI service — wraps run_agent() and exposes thread_id for multi-tenancy.

Difference vs Claude Agent SDK main.py:
  Claude SDK  — POST /agent/run returns {"status", "result"}.  No session concept.
  DeepAgents  — POST /agent/run returns {"status", "result", "thread_id"}.
                Client passes thread_id back to continue the same session.
                Built-in multi-tenancy: each thread_id has its own isolated state.
"""
import base64
import os
import tempfile
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import agent as _agent_mod
from agent import build_agent, run_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    _agent_mod._agent = build_agent()
    print("Scholarship agent (DeepAgents) ready.")
    yield


app = FastAPI(title="Scholarship Agent (DeepAgents)", lifespan=lifespan)


class AgentRequest(BaseModel):
    resume_base64: str
    recipient_email: str
    thread_id: Optional[str] = None   # omit to start a new session; pass to resume one


class AgentResponse(BaseModel):
    status: str
    recipient_email: str
    result: str
    thread_id: str                     # return to client so they can resume this session


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/agent/run", response_model=AgentResponse)
async def run(req: AgentRequest):
    if not req.recipient_email.strip():
        raise HTTPException(status_code=400, detail="recipient_email cannot be empty.")

    pdf_bytes = base64.b64decode(req.resume_base64)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        tmp_path = f.name

    try:
        result, thread_id = await run_agent(tmp_path, req.recipient_email, req.thread_id)
    finally:
        os.unlink(tmp_path)

    return AgentResponse(
        status="completed",
        recipient_email=req.recipient_email,
        result=result,
        thread_id=thread_id,
    )
