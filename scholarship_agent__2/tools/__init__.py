from claude_agent_sdk import create_sdk_mcp_server

from .save_report import save_report
from .send_email import send_email

scholarship_mcp_server = create_sdk_mcp_server(
    name="scholarship-tools",
    version="2.0.0",
    tools=[save_report, send_email],
)

MCP_SERVER_KEY = "scholarship"

ALLOWED_TOOLS = [
    f"mcp__{MCP_SERVER_KEY}__save_report",
    f"mcp__{MCP_SERVER_KEY}__send_email",
]
