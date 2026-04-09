"""Confluence auto-sync background service.

Polls Confluence for version changes on imported pages and resets them to
'pending' so the document worker re-imports them.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from config import settings

logger = logging.getLogger(__name__)


class ConfluenceSyncService:
    def __init__(self, pool, confluence_service):
        self._pool = pool
        self._confluence = confluence_service
        self._interval = settings.CONFLUENCE_SYNC_INTERVAL
        self._batch_size = settings.CONFLUENCE_SYNC_BATCH_SIZE
        self._running = False

    async def start(self):
        if not settings.CONFLUENCE_SYNC_ENABLED:
            logger.info("Confluence sync disabled")
            return
        self._running = True
        logger.info("Confluence sync started (interval=%ds, batch=%d)", self._interval, self._batch_size)
        while self._running:
            try:
                await self._poll_cycle()
            except Exception:
                logger.exception("Confluence sync cycle failed")
            await asyncio.sleep(self._interval)

    def stop(self):
        self._running = False

    async def _poll_cycle(self):
        rows = await self._pool.fetch(
            "SELECT id::text, metadata "
            "FROM documents "
            "WHERE parser = 'confluence' AND NOT archived AND status = 'ready' "
            "  AND metadata->>'confluence_page_id' IS NOT NULL "
            "ORDER BY COALESCE(metadata->>'confluence_last_synced_at', '1970-01-01') ASC "
            "LIMIT $1",
            self._batch_size,
        )
        if not rows:
            return

        updated = 0
        for row in rows:
            metadata = row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"] or "{}")
            page_id = metadata.get("confluence_page_id")
            stored_version = metadata.get("confluence_version", 0)
            if not page_id:
                continue

            current_version = await self._confluence.check_page_version(page_id)
            now_utc = datetime.now(timezone.utc).isoformat()

            if current_version is None:
                # API error — update sync timestamp to avoid hammering
                await self._pool.execute(
                    "UPDATE documents SET metadata = metadata || $2::jsonb WHERE id = $1",
                    row["id"], json.dumps({"confluence_last_synced_at": now_utc}),
                )
                continue

            if current_version > stored_version:
                logger.info("Page %s updated: v%d→v%d, re-queuing doc %s", page_id, stored_version, current_version, row["id"][:8])
                await self._pool.execute(
                    "UPDATE documents SET status = 'pending', error_message = NULL, "
                    "metadata = metadata || $2::jsonb, updated_at = now() WHERE id = $1",
                    row["id"], json.dumps({"confluence_last_synced_at": now_utc}),
                )
                updated += 1
            else:
                await self._pool.execute(
                    "UPDATE documents SET metadata = metadata || $2::jsonb WHERE id = $1",
                    row["id"], json.dumps({"confluence_last_synced_at": now_utc}),
                )

        if updated:
            logger.info("Confluence sync: %d/%d pages re-queued", updated, len(rows))
