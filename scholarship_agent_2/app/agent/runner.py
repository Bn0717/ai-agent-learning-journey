"""
Scholarship Agent — Claude Agent SDK orchestrator.

Claude is the orchestrator. This module:
  - Reads CLAUDE.md as the system-prompt source of truth
  - Creates the in-process MCP server with all 9 tools
  - Exposes `run_agent()` for single queries (FastAPI /chat endpoint)
  - Exposes `run_agent_stream()` for streaming (SSE / WebSocket)
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import AsyncIterator

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, McpSdkServerConfig
from claude_agent_sdk.types import (
    AssistantMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
)

from app.tools.scholarship_tools import create_scholarship_mcp_server

logger = logging.getLogger(__name__)

# Load CLAUDE.md system prompt
_CLAUDE_MD_PATH = Path(__file__).parent.parent.parent / "CLAUDE.md"


def _load_system_prompt() -> str:
    if _CLAUDE_MD_PATH.exists():
        return _CLAUDE_MD_PATH.read_text(encoding="utf-8")
    return "You are a helpful scholarship assistant."


def _build_options() -> ClaudeAgentOptions:
    mcp_server = create_scholarship_mcp_server()
    return ClaudeAgentOptions(
        mcp_servers=[
            McpSdkServerConfig(
                type="sdk",
                name="scholarship-tools",
                instance=mcp_server,
            )
        ],
        system_prompt=_load_system_prompt(),
        allowed_tools=[
            "save_student_profile",
            "get_student_profile",
            "search_internal_scholarships",
            "search_web_scholarships",
            "check_eligibility",
            "rank_scholarships",
            "generate_essay",
            "get_deadlines",
            "send_email_notification",
        ],
        max_turns=20,
    )


async def run_agent(prompt: str) -> dict:
    """
    Run the agent for a single prompt and return the final text response.

    Returns:
        {
            "response": str,          # final assistant text
            "tool_calls": list[str],  # names of tools invoked
            "cost_usd": float | None,
        }
    """
    options = _build_options()
    response_parts: list[str] = []
    tool_calls: list[str] = []
    cost_usd: float | None = None

    async with ClaudeSDKClient(options=options) as client:
        async for message in client.query(prompt=prompt):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_parts.append(block.text)
                    elif hasattr(block, "name"):
                        # ToolUseBlock
                        tool_calls.append(block.name)
            elif isinstance(message, ResultMessage):
                if hasattr(message, "cost_usd"):
                    cost_usd = message.cost_usd

    return {
        "response": "".join(response_parts),
        "tool_calls": tool_calls,
        "cost_usd": cost_usd,
    }


async def run_agent_stream(prompt: str) -> AsyncIterator[str]:
    """
    Stream agent responses token-by-token for SSE / WebSocket endpoints.

    Yields plain text chunks as they arrive.
    """
    options = _build_options()

    async with ClaudeSDKClient(options=options) as client:
        async for message in client.query(prompt=prompt):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        yield block.text
            elif isinstance(message, SystemMessage):
                logger.debug("Agent loop started (subtype=%s)", message.subtype)


async def run_agent_with_session(
    session_id: str,
    prompt: str,
) -> dict:
    """
    Stateful multi-turn agent using ClaudeSDKClient sessions.
    Call repeatedly with the same session_id to maintain conversation context.
    """
    options = _build_options()

    response_parts: list[str] = []
    tool_calls: list[str] = []

    async with ClaudeSDKClient(options=options) as client:
        async for message in client.query(
            prompt=prompt,
            session_id=session_id,
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_parts.append(block.text)
                    elif hasattr(block, "name"):
                        tool_calls.append(block.name)

    return {
        "session_id": session_id,
        "response": "".join(response_parts),
        "tool_calls": tool_calls,
    }
