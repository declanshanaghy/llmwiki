"""Stdio MCP server for local CLI usage (Claude Code, etc).

Runs the same tools as the HTTP server but over stdio transport,
using SUPAVAULT_USER_ID env var instead of OAuth.
"""

import sys
from mcp.server.fastmcp import FastMCP
from config import settings
from tools import register

mcp = FastMCP(
    "LLM Wiki (local)",
    instructions=(
        "You are connected to an LLM Wiki workspace. The user has uploaded files, notes, "
        "and documents that you can read, search, edit, and organize. Your job is to work "
        "with these materials — answer questions, take notes, and compile structured wiki "
        "pages from the raw sources. Call the `guide` tool first to see available knowledge "
        "bases and learn the full workflow."
    ),
)

register(mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio")
