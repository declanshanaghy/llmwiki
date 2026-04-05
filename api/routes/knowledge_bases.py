import re
import secrets
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import settings
from deps import get_scoped_db
from scoped_db import ScopedDB

router = APIRouter(prefix="/v1/knowledge-bases", tags=["knowledge-bases"])


class CreateKnowledgeBase(BaseModel):
    name: str
    description: str | None = None


class UpdateKnowledgeBase(BaseModel):
    name: str | None = None
    description: str | None = None


class KnowledgeBaseOut(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    slug: str
    description: str | None = None
    source_count: int = 0
    wiki_page_count: int = 0
    created_at: datetime
    updated_at: datetime


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug).strip("-")
    return slug or "kb"


async def _unique_slug(db: ScopedDB, name: str) -> str:
    slug = _slugify(name)
    exists = await db.fetchval(
        "SELECT 1 FROM knowledge_bases WHERE slug = $1 AND user_id = auth.uid()",
        slug,
    )
    if exists:
        slug = f"{slug}-{secrets.token_hex(3)}"
    return slug


@router.get("", response_model=list[KnowledgeBaseOut])
async def list_knowledge_bases(db: Annotated[ScopedDB, Depends(get_scoped_db)]):
    rows = await db.fetch(
        "SELECT kb.id, kb.user_id, kb.name, kb.slug, kb.description, "
        "  kb.created_at, kb.updated_at, "
        "  (SELECT COUNT(*) FROM documents d "
        "   WHERE d.knowledge_base_id = kb.id AND d.path NOT LIKE '/wiki/%%' AND NOT d.archived) AS source_count, "
        "  (SELECT COUNT(*) FROM documents d "
        "   WHERE d.knowledge_base_id = kb.id AND d.path LIKE '/wiki/%%' AND NOT d.archived) AS wiki_page_count "
        "FROM knowledge_bases kb ORDER BY kb.updated_at DESC"
    )
    return rows


@router.post("", response_model=KnowledgeBaseOut, status_code=201)
async def create_knowledge_base(
    body: CreateKnowledgeBase,
    db: Annotated[ScopedDB, Depends(get_scoped_db)],
):
    user_count = await db.fetchval("SELECT COUNT(DISTINCT id) FROM users")
    if user_count and user_count >= settings.GLOBAL_MAX_USERS:
        raise HTTPException(
            status_code=503,
            detail="We've reached our user capacity for now. Please try again later.",
        )
    slug = await _unique_slug(db, body.name)
    row = await db.fetchrow(
        "INSERT INTO knowledge_bases (user_id, name, slug, description) "
        "VALUES (auth.uid(), $1, $2, $3) "
        "RETURNING id, user_id, name, slug, description, created_at, updated_at",
        body.name,
        slug,
        body.description,
    )
    return row


@router.get("/{kb_id}", response_model=KnowledgeBaseOut)
async def get_knowledge_base(
    kb_id: UUID,
    db: Annotated[ScopedDB, Depends(get_scoped_db)],
):
    row = await db.fetchrow(
        "SELECT kb.id, kb.user_id, kb.name, kb.slug, kb.description, "
        "  kb.created_at, kb.updated_at, "
        "  (SELECT COUNT(*) FROM documents d "
        "   WHERE d.knowledge_base_id = kb.id AND d.path NOT LIKE '/wiki/%%' AND NOT d.archived) AS source_count, "
        "  (SELECT COUNT(*) FROM documents d "
        "   WHERE d.knowledge_base_id = kb.id AND d.path LIKE '/wiki/%%' AND NOT d.archived) AS wiki_page_count "
        "FROM knowledge_bases kb WHERE kb.id = $1",
        kb_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return row


@router.patch("/{kb_id}", response_model=KnowledgeBaseOut)
async def update_knowledge_base(
    kb_id: UUID,
    body: UpdateKnowledgeBase,
    db: Annotated[ScopedDB, Depends(get_scoped_db)],
):
    updates = []
    params = []
    idx = 1

    if body.name is not None:
        updates.append(f"name = ${idx}")
        params.append(body.name)
        idx += 1
    if body.description is not None:
        updates.append(f"description = ${idx}")
        params.append(body.description)
        idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = now()")
    params.append(kb_id)

    sql = (
        f"UPDATE knowledge_bases SET {', '.join(updates)} "
        f"WHERE id = ${idx} "
        f"RETURNING id, user_id, name, slug, description, created_at, updated_at"
    )
    row = await db.fetchrow(sql, *params)
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return row


@router.delete("/{kb_id}", status_code=204)
async def delete_knowledge_base(
    kb_id: UUID,
    db: Annotated[ScopedDB, Depends(get_scoped_db)],
):
    result = await db.execute(
        "DELETE FROM knowledge_bases WHERE id = $1",
        kb_id,
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Knowledge base not found")
