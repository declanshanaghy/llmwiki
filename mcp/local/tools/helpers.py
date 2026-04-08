"""Local MCP tool helpers.

get_user_id returns the fixed local user — no token checks, no env var bypass.
Pure utility functions are imported from the shared helpers module.
"""

import os
import uuid

from mcp.server.fastmcp import Context

# Pure utilities — shared between local and hosted, no auth logic
from tools.helpers import deep_link, resolve_path, glob_match, parse_page_range, MAX_LIST, MAX_SEARCH

_LOCAL_USER_ID = os.environ.get(
    "LLMWIKI_USER_ID",
    str(uuid.uuid5(uuid.NAMESPACE_DNS, "local")),
)


def get_user_id(ctx: Context) -> str:
    """Return the fixed local user ID. No auth, no token, no bypass checks."""
    return _LOCAL_USER_ID
