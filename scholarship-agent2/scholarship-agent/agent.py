# -*- coding: utf-8 -*-
"""
Scholarship Advisor Agent — Claude Code Agent SDK
Run directly:  python agent.py --resume path/to/resume.pdf --email student@example.com
Or via API:    uvicorn main:app (see main.py)
"""

import asyncio
import sys
import time
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    UserMessage,
    query,
)
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

load_dotenv()

PROJECT_DIR = Path(__file__).parent.resolve()
console = Console()


def _input_summary(tool_name: str, inp: dict) -> str:
    if tool_name == "Bash" and "command" in inp:
        return inp["command"].strip().replace("\n", "; ")[:90]
    if tool_name in ("WebSearch", "web_search") and "query" in inp:
        return inp["query"][:90]
    if tool_name in ("WebFetch", "web_fetch") and "url" in inp:
        return inp["url"][:90]
    if "file_path" in inp:
        return inp["file_path"][:90]
    for v in inp.values():
        return str(v).replace("\n", " ")[:90]
    return ""


def _result_snippet(content) -> str:
    if content is None:
        return "(no output)"
    if isinstance(content, list):
        parts = [
            item["text"] if isinstance(item, dict) and item.get("type") == "text"
            else str(item)
            for item in content
        ]
        text = " ".join(parts)
    else:
        text = str(content)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    snippet = lines[0][:100] if lines else "(empty)"
    return f"{snippet}  [{len(text):,} chars]"


async def run_agent(resume_path: str, recipient_email: str) -> str:
    prompt = f"""
Find the best scholarships for the student whose resume is at: {resume_path}
Email the final report to: {recipient_email}

Use your available skills to complete the full workflow.
"""

    console.print(
        Panel.fit(
            f"[bold cyan]SCHOLARSHIP ADVISOR AGENT[/bold cyan]\n"
            f"[dim]Resume  :[/dim] [yellow]{resume_path}[/yellow]\n"
            f"[dim]Email   :[/dim] [yellow]{recipient_email}[/yellow]\n"
            f"[dim]Model   :[/dim] [green]claude-sonnet-4-6[/green]",
            border_style="cyan",
            padding=(0, 2),
        )
    )
    console.print()

    pending: dict[str, str] = {}
    turn = 0
    tool_count = 0
    result_text = ""
    wall_start = time.monotonic()

    async for msg in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["WebSearch", "WebFetch", "Bash", "Write", "Edit", "Read"],
            model="claude-sonnet-4-6",
            cwd=str(PROJECT_DIR),
        ),
    ):
        if isinstance(msg, AssistantMessage) and msg.content:
            tool_blocks = [
                b for b in msg.content
                if hasattr(b, "id") and hasattr(b, "name") and hasattr(b, "input")
            ]
            if tool_blocks:
                turn += 1
                console.rule(f"[bold]Turn {turn}[/bold]", style="bright_black")
                for block in tool_blocks:
                    summary = _input_summary(block.name, block.input)
                    pending[block.id] = block.name
                    tool_count += 1
                    console.print(
                        f"  [bold magenta]▶[/bold magenta] "
                        f"[bold white]{block.name:<20}[/bold white]"
                        f"[dim]{summary}[/dim]"
                    )

        elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
            for block in msg.content:
                if not (hasattr(block, "tool_use_id") and hasattr(block, "content")):
                    continue
                is_err = getattr(block, "is_error", False)
                snippet = _result_snippet(block.content)
                icon = "[red]✗[/red]" if is_err else "[green]✓[/green]"
                console.print(f"    {icon} [dim]{snippet}[/dim]")
                pending.pop(block.tool_use_id, None)

        elif isinstance(msg, ResultMessage):
            result_text = msg.result or ""
            elapsed = time.monotonic() - wall_start

            console.print()
            console.rule("[bold green]Result[/bold green]", style="green")
            console.print(result_text)

            usage = msg.usage or {}
            in_tok = usage.get("input_tokens", 0)
            out_tok = usage.get("output_tokens", 0)
            api_s = getattr(msg, "duration_api_ms", 0) / 1000
            cost = msg.total_cost_usd

            console.print()
            console.rule("[bold]Stats[/bold]", style="bright_black")
            tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
            tbl.add_column(style="dim", width=16)
            tbl.add_column(style="bold white")
            tbl.add_row("Wall time", f"{elapsed:.1f}s  (API {api_s:.1f}s)")
            tbl.add_row("Turns", str(msg.num_turns))
            tbl.add_row("Tools called", str(tool_count))
            tbl.add_row("Tokens in/out", f"{in_tok:,} / {out_tok:,}")
            if cost is not None:
                tbl.add_row("Est. cost", f"${cost:.4f}")
            if msg.is_error and msg.errors:
                tbl.add_row("[red]Errors[/red]", "\n".join(msg.errors))
            console.print(tbl)

    return result_text


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Scholarship Advisor Agent")
    parser.add_argument("--resume", default=os.getenv("RESUME_PATH"), help="Path to the student's PDF resume")
    parser.add_argument("--email", default=os.getenv("RECIPIENT_EMAIL"), help="Recipient email address")
    args = parser.parse_args()

    if not args.resume:
        print("Error: provide --resume or set RESUME_PATH in .env")
        sys.exit(1)
    if not args.email:
        print("Error: provide --email or set RECIPIENT_EMAIL in .env")
        sys.exit(1)

    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(run_agent(args.resume, args.email))
