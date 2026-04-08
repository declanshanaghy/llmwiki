import json
from typing import Annotated, AsyncGenerator

from fastapi import Depends, Request

from config import settings
from scoped_db import ScopedDB


def _quote_literal(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


async def get_pool(request: Request):
    return request.app.state.pool


async def get_user_id(request: Request) -> str:
    """Authenticate and return user_id."""
    auth_provider = request.app.state.auth_provider
    if auth_provider:
        return await auth_provider.get_current_user(request)
    # Hosted mode: use Supabase JWKS auth
    from auth import get_current_user
    return await get_current_user(request)


async def get_scoped_db(
    request: Request,
    pool: Annotated = Depends(get_pool),
) -> AsyncGenerator[ScopedDB, None]:
    """Read-only scoped DB with RLS enforced. Hosted mode only."""
    if request.app.state.mode == "local":
        # Local mode: no RLS, return a thin wrapper around SQLite
        db = request.app.state.sqlite_db
        user_id = await get_user_id(request)
        yield ScopedDB(None, db, user_id)
        return

    from auth import get_current_user
    user_id = await get_current_user(request)
    conn = await pool.acquire()
    tr = conn.transaction()
    await tr.start()
    try:
        claims = json.dumps({"sub": user_id})
        await conn.execute("SET LOCAL ROLE authenticated")
        await conn.execute(f"SET LOCAL request.jwt.claims = {_quote_literal(claims)}")
        yield ScopedDB(pool, conn, user_id)
        await tr.commit()
    except Exception:
        await tr.rollback()
        raise
    finally:
        await pool.release(conn)
