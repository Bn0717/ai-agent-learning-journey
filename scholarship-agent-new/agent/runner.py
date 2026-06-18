from claude_agent_sdk import query, ClaudeAgentOptions

from tools.web_search import web_search_tool
from tools.database import save_to_db_tool
from tools.email_tool import send_email_tool


TOOLS = [
    web_search_tool,
    save_to_db_tool,
    send_email_tool
]


async def run_agent(user_input: str):

    options = ClaudeAgentOptions(
        tools=TOOLS,
        system_prompt="""
You are a scholarship AI agent.
You help users find scholarships, store results, and send summaries.
Use tools when needed.
"""
    )

    response = await query(
        prompt=user_input,
        options=options
    )

    return response