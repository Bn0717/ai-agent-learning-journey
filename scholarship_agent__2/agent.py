import asyncio
from pathlib import Path
from typing import AsyncIterator
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage, SystemMessage
from claude_agent_sdk.types import TextBlock
from tools import scholarship_mcp_server, ALLOWED_TOOLS, MCP_SERVER_KEY
from config import settings
from scholarship_engine import load_student, search_and_rank

_CLAUDE_MD = Path(__file__).parent / "CLAUDE.md"


def _system_prompt() -> str:
    return _CLAUDE_MD.read_text(encoding="utf-8") if _CLAUDE_MD.exists() else (
        "You are a Scholarship Report Writer. Annotate, save, and email pre-ranked scholarships."
    )


def _auth_env() -> dict[str, str]:
    return settings.vertex_env() if settings.use_vertex else settings.anthropic_env()


def _build_prompt(student: dict, ranked: list[dict]) -> str:
    """Build a data-rich prompt; Python already did search + ranking."""
    header = (
        f"Student    : {student['name']} (ID: {student['id']})\n"
        f"GPA        : {student['gpa']}\n"
        f"Field      : {student['field_of_study']}\n"
        f"Nationality: {student['nationality']}\n"
        f"Interests  : {', '.join(student.get('interests', []))}\n"
        f"Email      : {student['email']}\n"
    )
    if not ranked:
        return header + "\nNo eligible scholarships found for this student's profile."

    rows = "\n".join(
        f"#{i+1}  {s['name']} | ${s['amount_usd']:,} | Deadline: {s['deadline']} | "
        f"Provider: {s['provider']} | Score: {s['_score']}"
        for i, s in enumerate(ranked)
    )
    return (
        f"{header}\n"
        f"Pre-ranked eligible scholarships ({len(ranked)} total, best first):\n"
        f"{rows}\n\n"
        f"Follow your instructions: write one ≤50-word bullet per scholarship, "
        f"then call save_report, then send_email to {student['email']}."
    )


async def stream_agent(
    student_id: str | None = None,
    custom_prompt: str | None = None,
) -> AsyncIterator[dict]:
    """Yield agent events. Python handles search/ranking; agent only annotates + saves."""
    if student_id:
        student = load_student(student_id)
        ranked  = search_and_rank(student)
        prompt  = _build_prompt(student, ranked)
        print(f"[pre-process] {len(ranked)} scholarships ranked for {student['name']}", flush=True)
    else:
        prompt = custom_prompt or "Help me find scholarships."

    options = ClaudeAgentOptions(
        system_prompt=_system_prompt(),
        mcp_servers={MCP_SERVER_KEY: scholarship_mcp_server},
        allowed_tools=ALLOWED_TOOLS,
        permission_mode="bypassPermissions",
        max_turns=5,
        env=_auth_env(),
        stderr=lambda line: print(f"[SDK stderr] {line}", flush=True),
    )

    async for message in query(prompt=prompt, options=options):
        # 🧠 Assistant messages (Claude thinking / tool calls)
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    yield {
                        "type": "text",
                        "content": block.text
                    }

                elif hasattr(block, "name") and hasattr(block, "input"):
                    print(f"[DEBUG] TOOL CALL: {block.name}")
                    print(f"[TOOL INPUT SEEN] {block.input}")

                    yield {
                        "type": "tool_call",
                        "tool": block.name,
                        "input": getattr(block, "input", {})
                    }

        # 🧠 DEBUG: Final result
        elif isinstance(message, ResultMessage):
            print("\n[DEBUG] FINAL RESULT REACHED")

            yield {
                "type": "result",
                "status": "error" if message.is_error else "success",
                "result": message.result,
                "session_id": message.session_id,
                "num_turns": message.num_turns,
                "total_cost_usd": message.total_cost_usd,
            }

        # 🧠 DEBUG: system messages (skip noisy debug output)
        elif isinstance(message, SystemMessage):
            # Skip printing init, thinking_tokens, and other system messages for cleaner output
            yield {
                "type": "system",
                "subtype": message.subtype,
                "data": message.data
            }


async def run_agent(
    student_id: str | None = None,
    custom_prompt: str | None = None,
) -> dict:
    """Run the agent to completion and return the aggregated result."""
    messages: list[dict] = []
    final_result: dict = {}

    async for event in stream_agent(student_id=student_id, custom_prompt=custom_prompt):
        messages.append(event)
        if event["type"] == "result":
            final_result = event

    return {
        "status": final_result.get("status", "unknown"),
        "result": final_result.get("result"),
        "session_id": final_result.get("session_id"),
        "num_turns": final_result.get("num_turns"),
        "total_cost_usd": final_result.get("total_cost_usd"),
        "messages": messages,
    }


if __name__ == "__main__":
    import sys

    sid = sys.argv[1] if len(sys.argv) > 1 else "S001"

    student = load_student(sid)
    ranked  = search_and_rank(student)
    print(f"Student : {student['name']} (GPA {student['gpa']}, {student['field_of_study']})")
    print(f"Eligible: {len(ranked)} scholarships\n")
    for i, s in enumerate(ranked):
        print(f"  #{i+1}  {s['name']} — ${s['amount_usd']:,}  (score {s['_score']})")
    print()

    result = asyncio.run(run_agent(student_id=sid))
    print(f"\nStatus : {result['status']}")
    print(f"Turns  : {result['num_turns']}")
    print(f"Cost   : ${result['total_cost_usd'] or 0:.4f}")
    print(f"\nFinal result:\n{result['result']}")
