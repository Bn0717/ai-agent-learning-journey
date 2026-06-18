import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from anthropic import AnthropicVertex
import uvicorn

from tools.database import init_db, get_student_profile, search_internal_scholarships
from tools.web_research import search_web_scholarships
from tools.eligibility_checker import check_eligibility
from tools.essay_writer import write_essay
from tools.tracker import track_scholarship, get_tracked_scholarships, update_scholarship_status
from tools.email_sender import send_email

load_dotenv()

app = FastAPI(title='Scholarship Agent v2')

PROJECT_ID = os.getenv('GCP_PROJECT_ID', 'brain-433706')
REGION     = os.getenv('GCP_REGION', 'asia-southeast1')
MODEL      = 'claude-3-5-sonnet@20240620'

SYSTEM_PROMPT = """You are an intelligent scholarship research assistant. Help students find, evaluate, and apply for scholarships.

When given a student ID, always start by fetching their profile so you can personalise your research.
Then search both internal and web scholarships, check eligibility, track the best matches, and email the results.
Be proactive — use tools without waiting to be asked. Complete the full workflow in one go."""

TOOLS = [
    {
        "name": "get_student_profile",
        "description": "Fetch a student's profile (name, nationality, degree level, CGPA, email) from the database.",
        "input_schema": {
            "type": "object",
            "properties": {"student_id": {"type": "string", "description": "Student ID e.g. STU001"}},
            "required": ["student_id"],
        },
    },
    {
        "name": "search_internal_scholarships",
        "description": "Search the internal scholarship database by field of study, nationality, or degree level.",
        "input_schema": {
            "type": "object",
            "properties": {
                "field_of_study": {"type": "string"},
                "nationality":    {"type": "string"},
                "degree_level":   {"type": "string"},
            },
        },
    },
    {
        "name": "search_web_scholarships",
        "description": "Search the web for real, currently open external scholarships matching the query.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "e.g. 'Computer Science scholarships for Malaysian undergraduates 2026'"}},
            "required": ["query"],
        },
    },
    {
        "name": "check_eligibility",
        "description": "Check whether a student meets the requirements for a specific scholarship.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_profile": {"type": "object", "description": "Student profile dict from get_student_profile"},
                "scholarship":     {"type": "object", "description": "Scholarship dict with fields like min_cgpa, nationality, degree_level"},
            },
            "required": ["student_profile", "scholarship"],
        },
    },
    {
        "name": "write_essay",
        "description": "Draft a personalised scholarship application essay based on the student's profile.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scholarship_name": {"type": "string"},
                "student_profile":  {"type": "object"},
                "essay_prompt":     {"type": "string", "description": "The essay question or prompt (optional)"},
            },
            "required": ["scholarship_name", "student_profile"],
        },
    },
    {
        "name": "track_scholarship",
        "description": "Save a scholarship to the student's tracker in the database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id":       {"type": "string"},
                "scholarship_name": {"type": "string"},
                "provider":         {"type": "string"},
                "deadline":         {"type": "string"},
                "application_link": {"type": "string"},
                "status":           {"type": "string", "enum": ["interested", "applied", "pending", "awarded", "rejected"]},
            },
            "required": ["student_id", "scholarship_name", "provider"],
        },
    },
    {
        "name": "get_tracked_scholarships",
        "description": "Retrieve all scholarships currently tracked for a student.",
        "input_schema": {
            "type": "object",
            "properties": {"student_id": {"type": "string"}},
            "required": ["student_id"],
        },
    },
    {
        "name": "update_scholarship_status",
        "description": "Update the application status of a tracked scholarship.",
        "input_schema": {
            "type": "object",
            "properties": {
                "track_id": {"type": "integer"},
                "status":   {"type": "string", "enum": ["interested", "applied", "pending", "awarded", "rejected"]},
            },
            "required": ["track_id", "status"],
        },
    },
    {
        "name": "send_email",
        "description": "Send scholarship findings or an essay draft to a student's email address.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient_email": {"type": "string"},
                "subject":         {"type": "string"},
                "body":            {"type": "string", "description": "Email body in markdown format"},
            },
            "required": ["recipient_email", "subject", "body"],
        },
    },
]

TOOL_MAP = {
    "get_student_profile":          get_student_profile,
    "search_internal_scholarships": search_internal_scholarships,
    "search_web_scholarships":      search_web_scholarships,
    "check_eligibility":            check_eligibility,
    "write_essay":                  write_essay,
    "track_scholarship":            track_scholarship,
    "get_tracked_scholarships":     get_tracked_scholarships,
    "update_scholarship_status":    update_scholarship_status,
    "send_email":                   send_email,
}


def run_agent(query: str, student_id: str = None) -> dict:
    client = AnthropicVertex(project_id=PROJECT_ID, region=REGION)

    user_message = f"Student ID: {student_id}\n\n{query}" if student_id else query
    messages     = [{"role": "user", "content": user_message}]
    tools_used   = []

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            final_text = next((b.text for b in response.content if hasattr(b, "text")), "Agent completed.")
            return {"status": "ok", "response": final_text, "tools_used": tools_used}

        if response.stop_reason == "tool_use":
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    tools_used.append({"tool": block.name, "input": block.input})
                    fn = TOOL_MAP.get(block.name)
                    try:
                        result = fn(**block.input) if fn else {"error": f"Unknown tool: {block.name}"}
                    except Exception as e:
                        result = {"error": str(e)}
                    results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     json.dumps(result, default=str),
                    })
            messages.append({"role": "user", "content": results})

        else:
            return {"status": "stopped", "reason": response.stop_reason, "tools_used": tools_used}


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


class ResearchRequest(BaseModel):
    query: str
    student_id: str = None


@app.post("/research")
def research(req: ResearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")
    return run_agent(req.query, req.student_id)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
