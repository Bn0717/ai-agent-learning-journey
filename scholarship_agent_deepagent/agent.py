r"""
Setup (first time only):
  pip install deepagents langchain-anthropic httpx pdfplumber python-dotenv fastapi uvicorn

Run locally:
  python agent.py --resume path/to/resume.pdf --email recipient@example.com

── What this agent does ─────────────────────────────────────────────────────────
  Given a student resume and email, the main agent autonomously plans and executes
  a full scholarship matching workflow by selecting from 7 available skills.

  The agent calls write_todos to plan its own steps, then invokes skills as needed:
    fetch-scholarships      discover scholarships from the BASE Initiative website
    parse-resume            extract text + structured profile from the student PDF
    summarise-scholarship   summarise each scholarship into structured format
    assess-fit              score fit and identify gaps per scholarship
    rank-scholarships       rank by fit score, keep top 5
    generate-report         write markdown report to disk
    send-email              email the report to the student

── Key difference vs Claude Agent SDK ───────────────────────────────────────────
  Claude Agent SDK   CLAUDE.md tells the agent to use skills in a fixed order (1→7).
                     The agent follows the prescribed sequence — no self-planning.

  DeepAgents         AGENTS.md describes the goal and lists available skills.
                     The agent calls write_todos to plan its own steps, then picks
                     and invokes skills autonomously based on its plan.

── Framework comparison ─────────────────────────────────────────────────────────
  Feature                  Deep Agents                      Claude Agent SDK
  ──────────────────────────────────────────────────────────────────────────────
  Where agent runs         Sandbox or remote command exec   Inside a sandbox
  Execution backend        Pluggable: local / VFS / remote  Local sandbox filesystem
  Model provider           Any (Anthropic, OpenAI, Google…) Claude only
  Per-provider tuning      Harness profiles (beta)          Configure per call in code
  Deployment               LangSmith managed or             Self-host — you build the
                           langgraph build self-hosted       server, auth, and streaming
  Multi-tenancy            Built-in (thread_id, RBAC)       Build it yourself
  Planning                 write_todos — LLM self-plans      Skills used in fixed order
  Instructions file        AGENTS.md                        CLAUDE.md
  Skills directory         .deepagents/skills/              .claude/skills/
                           (YAML frontmatter required)       (# Skill: header only)
  Custom tools             bash(), web_fetch()              Bash, WebFetch (built-in)
  License                  MIT                              MIT (Claude Code proprietary)
"""

import argparse
import asyncio
import subprocess
import uuid
from pathlib import Path
from typing import Optional

import httpx
from deepagents import create_deep_agent, StateBackend
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent

SYSTEM_PROMPT = """You are a scholarship matching agent. Given a student's resume path and \
recipient email, autonomously complete a full scholarship matching workflow.

Start by calling write_todos to plan your steps. Then use your available skills to:
- Discover scholarships that match the student's education level
- Parse and understand the student's profile from their resume
- Assess how well the student fits each scholarship
- Generate a detailed, personalised report
- Email the report to the student

Read each skill's SKILL.md before using it. Use your judgement to decide the order \
and which skills to apply. Complete the full workflow before finishing."""


# ── Tools ──────────────────────────────────────────────────────────────────────
# Claude SDK gives Bash and WebFetch as built-in tools at no cost.
# DeepAgents requires you to define equivalent tools as Python functions.
# The payoff: with --sandbox modal these calls execute in a remote cloud sandbox
# (per-session isolation) instead of the shared local container shell.

def bash(command: str) -> str:
    """Run a shell command. Returns stdout + stderr combined."""
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, cwd=str(PROJECT_ROOT)
    )
    return (result.stdout + result.stderr).strip()


def web_fetch(url: str) -> str:
    """Fetch raw text content from a URL (first 10 000 chars)."""
    try:
        resp = httpx.get(
            url, timeout=30, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        return resp.text[:10_000]
    except Exception as e:
        return f"Error fetching {url}: {e}"


# ── Agent ──────────────────────────────────────────────────────────────────────
_agent = None


def build_agent():
    return create_deep_agent(
        model="anthropic:claude-sonnet-4-6",  # change to "openai:gpt-4o" — nothing else needed
        tools=[bash, web_fetch],
        skills=[str(PROJECT_ROOT / ".deepagents" / "skills")],
        checkpointer=MemorySaver(),   # enables thread_id session continuity
        backend=StateBackend(),
        system_prompt=SYSTEM_PROMPT,
    )


async def run_agent(
    resume_path: str,
    recipient_email: str,
    thread_id: Optional[str] = None,
) -> tuple[str, str]:
    global _agent
    if _agent is None:
        _agent = build_agent()

    thread_id = thread_id or str(uuid.uuid4())
    prompt = (
        f"Find the best scholarships for the student whose resume is at: {resume_path}\n"
        f"Email the final report to: {recipient_email}\n"
        "Use your available skills to complete the full workflow."
    )
    result = _agent.invoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    answer = result["messages"][-1].content
    return answer, thread_id


# ── CLI mode ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scholarship matching agent (DeepAgents)")
    parser.add_argument("--resume", required=True, help="Path to PDF resume")
    parser.add_argument("--email",  required=True, help="Recipient email address")
    parser.add_argument("--thread", default=None,  help="Thread ID to resume a prior session")
    args = parser.parse_args()

    result, thread_id = asyncio.run(run_agent(args.resume, args.email, args.thread))
    print(f"\nResult (thread: {thread_id}):\n{result}")
