"""
Scholarship Agent — Claude Code Agent SDK (Python) + Google Vertex AI
The agent reads CLAUDE.md to understand the 3 skills by name + description,
then decides which skill (.py) to call and in what order.

Setup:
    pip install claude-agent-sdk fastapi uvicorn

    # Google Vertex AI (no ANTHROPIC_API_KEY needed on Cloud Run)
    export CLAUDE_CODE_USE_VERTEX=1
    export GOOGLE_CLOUD_PROJECT=your-project-id
    export GOOGLE_CLOUD_LOCATION=asia-southeast1

    # Email
    export EMAIL_SENDER=you@gmail.com
    export EMAIL_PASSWORD=your-gmail-app-password

Run as a script:
    python agent.py

Run as FastAPI (matches your whiteboard):
    uvicorn agent:app --reload
    POST http://localhost:8000/find-scholarships
"""

import asyncio
import json
from claude_agent_sdk import query, ClaudeAgentOptions

# FastAPI layer (matches whiteboard: NextAPI → FastAPI → Agent)
from fastapi import FastAPI
from pydantic import BaseModel

# Import the 3 skill functions
from skills.web_search_scholarships import web_search_scholarships
from skills.save_to_database import save_to_database, query_from_database
from skills.send_scholarship_email import send_scholarship_email


# ── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(title="Scholarship Agent API")


class StudentProfile(BaseModel):
    name: str
    email: str
    field: str
    gpa: str
    nationality: str
    year: str
    background: str


@app.post("/find-scholarships")
async def find_scholarships(student: StudentProfile):
    """
    POST endpoint — triggered from your Next.js frontend.
    Runs the full agent loop: web search → DB → email.
    """
    result = await run_agent(student.model_dump())
    return {"status": "done", "summary": result}


@app.get("/scholarships/{email}")
async def get_scholarships(email: str):
    """GET saved scholarships for a student by email."""
    results = query_from_database(email)
    return {"email": email, "scholarships": results}


# ── Agent loop ───────────────────────────────────────────────────────────────

async def run_agent(student: dict) -> str:
    """
    Runs the Claude Agent SDK loop.
    CLAUDE.md tells the agent about each skill by name + description.
    The agent decides which skill to call and in what order.
    The actual skill .py functions are called after the agent instructs them.
    """

    prompt = f"""
A student needs scholarship matches. Their profile:

- Name       : {student['name']}
- Email      : {student['email']}
- Field      : {student['field']}
- GPA        : {student['gpa']}
- Nationality: {student['nationality']}
- Year       : {student['year']}
- Background : {student['background']}

Follow the workflow defined in CLAUDE.md:
1. Use web_search_scholarships to find matches
2. Use save_to_database to save the results
3. Use send_scholarship_email to notify the student

For each skill call, output a JSON block like:
SKILL_CALL: {{"skill": "web_search_scholarships", "args": {{...}}}}

Then I will execute the skill and give you the result.
Continue until all three skills are done.
"""

    print(f"\n🎓 Agent starting for {student['name']} ({student['email']})")
    print("=" * 60)

    final_result = ""
    skill_results = {}

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["WebSearch", "WebFetch", "Bash"],
            cwd=".",   # loads CLAUDE.md automatically
        ),
    ):
        if hasattr(message, "result") and message.result:
            final_result = message.result
            # Parse any SKILL_CALL instructions from the agent
            await _execute_skill_calls(message.result, student, skill_results)

        elif hasattr(message, "subtype") and message.subtype == "tool_use":
            tool = getattr(message, "tool_name", "tool")
            print(f"  ⚙️  Agent using: {tool}")

    print("\n✅ Agent finished!")
    return final_result


async def _execute_skill_calls(text: str, student: dict, results: dict):
    """Parse SKILL_CALL instructions from agent output and execute them."""
    import re
    calls = re.findall(r'SKILL_CALL:\s*(\{.*?\})', text, re.DOTALL)

    for call_json in calls:
        try:
            call = json.loads(call_json)
            skill_name = call.get("skill")
            args = call.get("args", {})

            print(f"\n  🔧 Executing skill: {skill_name}")

            if skill_name == "web_search_scholarships":
                results["scholarships"] = web_search_scholarships(
                    field=student["field"],
                    nationality=student["nationality"],
                    gpa=student["gpa"],
                    year=student["year"],
                    background=student["background"],
                )
                print(f"     Found {len(results['scholarships'])} scholarships")

            elif skill_name == "save_to_database":
                scholarships = results.get("scholarships", [])
                msg = save_to_database(student["email"], scholarships)
                print(f"     {msg}")

            elif skill_name == "send_scholarship_email":
                scholarships = results.get("scholarships", [])
                msg = send_scholarship_email(
                    student_name=student["name"],
                    student_email=student["email"],
                    scholarships=scholarships,
                )
                print(f"     {msg}")

        except (json.JSONDecodeError, KeyError) as e:
            print(f"  ⚠️  Skill parse error: {e}")


# ── Standalone script entry point ────────────────────────────────────────────

if __name__ == "__main__":
    STUDENT = {
        "name": "Alex Tan",
        "email": "alex@example.com",
        "field": "Computer Science",
        "gpa": "3.7",
        "nationality": "Malaysian",
        "year": "Undergraduate sophomore",
        "background": "First-generation college student, financial need",
    }
    asyncio.run(run_agent(STUDENT))
