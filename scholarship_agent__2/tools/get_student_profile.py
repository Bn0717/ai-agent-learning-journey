import json
from typing import Any
from claude_agent_sdk import tool
from config import DATA_DIR


@tool(
    "get_student_profile",
    "Retrieve a student's full profile including GPA, field of study, nationality, email, and interests.",
    {
        "type": "object",
        "properties": {
            "student_id": {
                "type": "string",
                "description": "The student's unique ID (e.g. 'S001')."
            }
        },
        "required": ["student_id"]
    },
)
async def get_student_profile(args: dict[str, Any]) -> dict[str, Any]:
    student_id = args.get("student_id", "").strip()
    students: list[dict] = json.loads((DATA_DIR / "students.json").read_text(encoding="utf-8"))

    student = next((s for s in students if s["id"] == student_id), None)
    if not student:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"error": f"Student '{student_id}' not found.", "available_ids": [s["id"] for s in students]})
            }]
        }

    return {"content": [{"type": "text", "text": json.dumps(student, indent=2)}]}
