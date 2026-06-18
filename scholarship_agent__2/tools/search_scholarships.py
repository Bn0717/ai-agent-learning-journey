import json
from typing import Any
from claude_agent_sdk import tool
from config import DATA_DIR


@tool(
    "search_scholarships",
    "Search the scholarship database by field of study, GPA, nationality, and keywords. "
    "Call at most 3 times total with different criteria. Stop immediately if you have 5 results. "
    "Do not repeat similar queries. Once you stop searching, proceed to ranking.",
    {
        "type": "object",
        "properties": {
            "field_of_study": {
                "type": "string",
                "description": "Field of study to filter by (e.g. 'Computer Science'). Leave empty for all fields."
            },
            "min_gpa": {
                "type": "number",
                "description": "Student's GPA (0.0–4.0). Only returns scholarships the student qualifies for."
            },
            "nationality": {
                "type": "string",
                "description": "Student's nationality (e.g. 'Malaysian'). Leave empty to include all."
            },
            "keywords": {
                "type": "string",
                "description": "Comma-separated keywords to match against scholarship name/description."
            }
        },
        "required": []
    },
)
async def search_scholarships(args: dict[str, Any]) -> dict[str, Any]:
    field = args.get("field_of_study", "").strip().lower()
    student_gpa = args.get("min_gpa", 0.0)
    nationality = args.get("nationality", "").strip().lower()
    keywords_raw = args.get("keywords", "").strip().lower()
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

    all_scholarships: list[dict] = json.loads((DATA_DIR / "scholarships.json").read_text(encoding="utf-8"))

    results = []
    for s in all_scholarships:
        # GPA eligibility check
        if student_gpa and s.get("min_gpa", 0) > student_gpa:
            continue

        # Field of study filter
        if field:
            scholarship_fields = [f.lower() for f in s.get("fields", [])]
            if "all" not in scholarship_fields and not any(field in sf or sf in field for sf in scholarship_fields):
                continue

        # Nationality filter
        if nationality:
            eligible = [n.lower() for n in s.get("eligible_nationalities", ["all"])]
            if "all" not in eligible and nationality not in eligible:
                continue

        # Keyword filter
        if keywords:
            haystack = (s.get("name", "") + " " + s.get("description", "")).lower()
            if not any(kw in haystack for kw in keywords):
                continue

        results.append(s)

    text = json.dumps({"count": len(results), "scholarships": results}, indent=2)
    return {"content": [{"type": "text", "text": text}]}
