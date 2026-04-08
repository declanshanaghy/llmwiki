"""Local delete tool — deletes files from disk and removes from SQLite index."""

from mcp.server.fastmcp import FastMCP, Context

from infra.db.sqlite import list_documents, get_document, archive_documents, get_workspace
from infra.storage.local import resolve_workspace_path
from .helpers import get_user_id, glob_match, resolve_path

_PROTECTED_FILES = {("/wiki/", "overview.md"), ("/wiki/", "log.md")}


def _is_protected(doc: dict) -> bool:
    return (doc.get("path", ""), doc.get("filename", "")) in _PROTECTED_FILES


async def _resolve_local_kb(user_id: str, slug: str) -> dict | None:
    ws = await get_workspace()
    if not ws:
        return None
    return {"id": ws["id"], "name": ws["name"], "slug": ws["name"]}


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="delete",
        description=(
            "Delete documents or wiki pages from the knowledge vault.\n\n"
            "Deletes the file from disk and removes it from the index.\n"
            "Note: overview.md and log.md are structural and cannot be deleted."
        ),
    )
    async def delete(
        ctx: Context,
        knowledge_base: str,
        path: str,
    ) -> str:
        user_id = get_user_id(ctx)

        kb = await _resolve_local_kb(user_id, knowledge_base)
        if not kb:
            return f"Knowledge base '{knowledge_base}' not found."

        if not path or path in ("*", "**", "**/*"):
            return "Error: refusing to delete everything. Use a more specific path."

        is_glob = "*" in path or "?" in path

        if is_glob:
            docs = await list_documents(user_id, kb["slug"])
            glob_pat = "/" + path.lstrip("/") if not path.startswith("/") else path
            matched = [d for d in docs if glob_match(d["path"] + d["filename"], glob_pat)]
        else:
            dir_path, filename = resolve_path(path)
            doc = await get_document(user_id, kb["slug"], filename, dir_path)
            matched = [doc] if doc else []

        if not matched:
            return f"No documents matching `{path}` found in {knowledge_base}."

        protected = [d for d in matched if _is_protected(d)]
        deletable = [d for d in matched if not _is_protected(d)]

        if not deletable:
            names = ", ".join(f"`{d['path']}{d['filename']}`" for d in protected)
            return f"Cannot delete {names} — these are structural wiki pages."

        # Delete files from disk first
        for d in deletable:
            relative = (d["path"].lstrip("/") + d["filename"])
            file_path = resolve_workspace_path(relative)
            if file_path and file_path.exists():
                file_path.unlink()

        # Then remove from index
        doc_ids = [str(d["id"]) for d in deletable]
        deleted_count = await archive_documents(doc_ids, user_id)

        lines = [f"Deleted {deleted_count} document(s):\n"]
        for d in deletable:
            lines.append(f"  {d['path']}{d['filename']}")

        if protected:
            names = ", ".join(f"`{d['path']}{d['filename']}`" for d in protected)
            lines.append(f"\nSkipped (protected): {names}")

        return "\n".join(lines)
