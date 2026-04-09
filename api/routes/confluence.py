import json
import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from config import settings
from deps import get_scoped_db, get_user_id
from scoped_db import ScopedDB
from services.confluence import _parse_page_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["confluence"])


class ConfluenceImportRequest(BaseModel):
    url: str
    include_children: bool = False


class ConfluenceChildrenRequest(BaseModel):
    url: str


class ConfluenceSpaceRequest(BaseModel):
    space_key: str


async def _queue_confluence_page(pool, kb_id: str, user_id: str, page_id: str, url: str, parent_page_id: str = "") -> bool:
    """Insert or re-queue a Confluence page for import. Returns True if queued (new), False if skipped (existing+ready)."""
    existing = await pool.fetchrow(
        "SELECT id::text, status FROM documents "
        "WHERE knowledge_base_id = $1 AND user_id = $2 AND NOT archived "
        "AND metadata->>'confluence_page_id' = $3",
        kb_id, user_id, page_id,
    )
    if existing:
        if existing["status"] in ("pending", "processing"):
            return False  # already in queue
        # Re-queue existing doc
        await pool.execute(
            "UPDATE documents SET status = 'pending', url = $2, error_message = NULL, updated_at = now() WHERE id = $1",
            existing["id"], url,
        )
        return True

    doc_id = str(uuid4())
    filename = url.rstrip("/").split("/")[-1] or "confluence-page"
    filename = filename[:100] + ".html"
    meta = {"confluence_page_id": page_id}
    if parent_page_id:
        meta["confluence_parent_id"] = parent_page_id
    metadata_json = json.dumps(meta)
    await pool.execute(
        "INSERT INTO documents (id, knowledge_base_id, user_id, filename, file_type, status, url, metadata, parser) "
        "VALUES ($1, $2, $3, $4, 'html', 'pending', $5, $6::jsonb, 'confluence')",
        doc_id, kb_id, user_id, filename, url, metadata_json,
    )
    return True


@router.post("/v1/knowledge-bases/{kb_id}/import/confluence", status_code=201)
async def import_confluence_page(
    kb_id: UUID,
    body: ConfluenceImportRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    request: Request,
):
    if not settings.CONFLUENCE_BASE_URL or not settings.CONFLUENCE_API_TOKEN:
        raise HTTPException(status_code=400, detail="Confluence credentials not configured on server")

    confluence_service = request.app.state.confluence_service
    if not confluence_service:
        raise HTTPException(status_code=501, detail="Confluence service not available")

    pool = request.app.state.pool

    # Verify KB ownership
    row = await pool.fetchrow(
        "SELECT id FROM knowledge_bases WHERE id = $1 AND user_id = $2",
        kb_id, user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # Deduplicate by Confluence page ID
    page_id = _parse_page_id(body.url)

    existing = await pool.fetchrow(
        "SELECT id::text FROM documents "
        "WHERE knowledge_base_id = $1 AND user_id = $2 AND NOT archived "
        "AND metadata->>'confluence_page_id' = $3",
        kb_id, user_id, page_id,
    )

    children_meta = json.dumps({"confluence_import_children": body.include_children})

    if existing:
        doc_id = existing["id"]
        await pool.execute(
            "UPDATE documents SET status = 'pending', parser = 'confluence', url = $2, error_message = NULL, "
            "metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb, updated_at = now() "
            "WHERE id = $1",
            doc_id, body.url, children_meta,
        )
    else:
        doc_id = str(uuid4())
        filename = body.url.rstrip("/").split("/")[-1] or "confluence-page"
        filename = filename[:100] + ".html"
        metadata_json = json.dumps({"confluence_page_id": page_id, "confluence_import_children": body.include_children})

        await pool.execute(
            "INSERT INTO documents (id, knowledge_base_id, user_id, filename, file_type, status, url, metadata, parser) "
            "VALUES ($1, $2, $3, $4, 'html', 'pending', $5, $6::jsonb, 'confluence')",
            doc_id, str(kb_id), user_id, filename, body.url, metadata_json,
        )

    # Worker picks up pending docs automatically

    # Return the document
    doc = await pool.fetchrow(
        "SELECT id, knowledge_base_id, user_id, filename, path, title, file_type, status, "
        "tags, date, metadata, error_message, version, document_number, archived, created_at, updated_at "
        "FROM documents WHERE id = $1",
        doc_id,
    )
    return dict(doc)


@router.post("/v1/documents/{doc_id}/reimport", status_code=200)
async def reimport_document(
    doc_id: UUID,
    user_id: Annotated[str, Depends(get_user_id)],
    request: Request,
):
    if not settings.CONFLUENCE_BASE_URL or not settings.CONFLUENCE_API_TOKEN:
        raise HTTPException(status_code=400, detail="Confluence credentials not configured on server")

    confluence_service = request.app.state.confluence_service
    if not confluence_service:
        raise HTTPException(status_code=501, detail="Confluence service not available")

    pool = request.app.state.pool

    doc = await pool.fetchrow(
        "SELECT id::text, user_id, knowledge_base_id::text as kb_id, url, parser "
        "FROM documents WHERE id = $1 AND user_id = $2 AND NOT archived",
        doc_id, user_id,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc["parser"] != "confluence" or not doc["url"]:
        raise HTTPException(status_code=400, detail="Document is not a Confluence import")

    await pool.execute(
        "UPDATE documents SET status = 'pending', error_message = NULL, updated_at = now() WHERE id = $1",
        doc_id,
    )

    # Worker picks up pending docs automatically

    row = await pool.fetchrow(
        "SELECT id, knowledge_base_id, user_id, filename, path, title, file_type, status, "
        "tags, date, metadata, error_message, version, document_number, archived, created_at, updated_at "
        "FROM documents WHERE id = $1",
        doc_id,
    )
    return dict(row)


@router.post("/v1/knowledge-bases/{kb_id}/import/confluence/children", status_code=200)
async def import_confluence_children(
    kb_id: UUID,
    body: ConfluenceChildrenRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    request: Request,
):
    """Import all child pages of a Confluence page."""
    if not settings.CONFLUENCE_BASE_URL or not settings.CONFLUENCE_API_TOKEN:
        raise HTTPException(status_code=400, detail="Confluence credentials not configured on server")

    confluence_service = request.app.state.confluence_service
    if not confluence_service:
        raise HTTPException(status_code=501, detail="Confluence service not available")

    pool = request.app.state.pool

    row = await pool.fetchrow(
        "SELECT id FROM knowledge_bases WHERE id = $1 AND user_id = $2",
        kb_id, user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    page_id = _parse_page_id(body.url)
    base = settings.CONFLUENCE_BASE_URL.rstrip("/")
    auth = (settings.CONFLUENCE_EMAIL, settings.CONFLUENCE_API_TOKEN)

    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        children = await confluence_service._fetch_children(client, base, auth, page_id)

    from urllib.parse import urlparse
    origin = f"{urlparse(base).scheme}://{urlparse(base).netloc}"

    queued = 0
    skipped = 0
    for child in children:
        child_id = str(child["id"])
        webui = child.get("_links", {}).get("webui", "")
        child_url = f"{origin}/wiki{webui}" if webui else f"{origin}/wiki/pages/{child_id}"
        if await _queue_confluence_page(pool, str(kb_id), user_id, child_id, child_url, parent_page_id=page_id):
            queued += 1
        else:
            skipped += 1

    return {"queued": queued, "skipped": skipped}


@router.post("/v1/knowledge-bases/{kb_id}/import/confluence/space", status_code=200)
async def import_confluence_space(
    kb_id: UUID,
    body: ConfluenceSpaceRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    request: Request,
):
    """Import all pages from a Confluence space."""
    if not settings.CONFLUENCE_BASE_URL or not settings.CONFLUENCE_API_TOKEN:
        raise HTTPException(status_code=400, detail="Confluence credentials not configured on server")

    confluence_service = request.app.state.confluence_service
    if not confluence_service:
        raise HTTPException(status_code=501, detail="Confluence service not available")

    pool = request.app.state.pool

    row = await pool.fetchrow(
        "SELECT id FROM knowledge_bases WHERE id = $1 AND user_id = $2",
        kb_id, user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    from urllib.parse import urlparse
    origin = f"{urlparse(settings.CONFLUENCE_BASE_URL).scheme}://{urlparse(settings.CONFLUENCE_BASE_URL).netloc}"

    pages = await confluence_service.fetch_space_pages(body.space_key)

    queued = 0
    skipped = 0
    for page in pages:
        page_url = f"{origin}/wiki{page['webui']}" if page.get("webui") else f"{origin}/wiki/pages/{page['id']}"
        if await _queue_confluence_page(pool, str(kb_id), user_id, page["id"], page_url):
            queued += 1
        else:
            skipped += 1

    return {"queued": queued, "skipped": skipped}
