import json
from datetime import datetime
from typing import Any
from claude_agent_sdk import tool
from config import REPORTS_DIR


@tool(
    "save_report",
    "Save the ranked scholarship report to disk. Returns the report_file path needed by send_email.",
    {
        "type": "object",
        "properties": {
            "student_id": {"type": "string", "description": "Student ID (e.g. S001)."},
            "student_name": {"type": "string", "description": "Student's full name."},
            "ranked_scholarships": {
                "type": "array",
                "description": "Ranked list. Each item: rank, name, amount_usd, deadline, provider, justification (≤50 words).",
                "items": {
                    "type": "object",
                    "properties": {
                        "rank":          {"type": "integer"},
                        "name":          {"type": "string"},
                        "amount_usd":    {"type": "number"},
                        "deadline":      {"type": "string"},
                        "provider":      {"type": "string"},
                        "justification": {"type": "string"},
                    },
                },
            },
        },
        "required": ["student_id", "student_name", "ranked_scholarships"],
    },
)
async def save_report(args: dict[str, Any]) -> dict[str, Any]:
    student_id = args.get("student_id", "unknown")
    student_name = args.get("student_name", "")
    scholarships = args.get("ranked_scholarships", [])
    now = datetime.now()

    report = {
        "generated_at": now.isoformat(),
        "student_id": student_id,
        "student_name": student_name,
        "ranked_scholarships": scholarships,
    }

    base = f"report_{student_id}_{now.strftime('%Y%m%d_%H%M%S')}"
    json_path = REPORTS_DIR / f"{base}.json"
    txt_path  = REPORTS_DIR / f"{base}.txt"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Python-generated text report — no LLM prose needed
    lines = [
        "=" * 60,
        "SCHOLARSHIP RECOMMENDATION REPORT",
        f"Generated : {now.strftime('%Y-%m-%d %H:%M')}",
        f"Student   : {student_name} ({student_id})",
        "=" * 60,
        "",
        "RANKED SCHOLARSHIPS",
        "-" * 40,
    ]
    for s in scholarships:
        lines += [
            f"",
            f"#{s.get('rank','?')}  {s.get('name','')}",
            f"    Provider : {s.get('provider','')}",
            f"    Award    : ${s.get('amount_usd', 0):,}",
            f"    Deadline : {s.get('deadline','N/A')}",
            f"    Why      : {s.get('justification','')}",
        ]

    txt_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "success": True,
                "report_file": str(json_path),
                "scholarships_saved": len(scholarships),
            }),
        }]
    }
