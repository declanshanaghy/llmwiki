"""Local guide tool — lists the workspace and provides wiki instructions."""

from mcp.server.fastmcp import FastMCP, Context

from config import settings
from infra.db.sqlite import list_knowledge_bases
from .helpers import get_user_id
from tools.guide import GUIDE_TEXT


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="guide",
        description="Get started with LLM Wiki. Call this to understand how the knowledge vault works and see your available knowledge bases.",
    )
    async def guide(ctx: Context) -> str:
        user_id = get_user_id(ctx)
        kbs = await list_knowledge_bases(user_id)
        if not kbs:
            return GUIDE_TEXT + "No workspace initialized. Run `llmwiki init <folder>` first."

        lines = []
        for kb in kbs:
            lines.append(f"- **{kb['name']}** (`{kb['slug']}`) — {kb['source_count']} sources, {kb['wiki_count']} wiki pages")
        return GUIDE_TEXT + "\n".join(lines)
