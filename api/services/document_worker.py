"""Generic document processing worker.

Polls the documents table for pending work and processes documents through
the appropriate pipeline (OCR for uploads, Confluence for imports).
Uses FOR UPDATE SKIP LOCKED for multi-host safe job claiming.
"""

import asyncio
import logging

from config import settings

logger = logging.getLogger(__name__)


class DocumentWorker:
    def __init__(self, pool, ocr_service, confluence_service=None):
        self._pool = pool
        self._ocr = ocr_service
        self._confluence = confluence_service
        self._interval = settings.WORKER_POLL_INTERVAL
        self._max_concurrent = settings.WORKER_MAX_CONCURRENT
        self._stale_timeout = settings.WORKER_STALE_TIMEOUT
        self._running = False
        self._in_flight = 0

    async def start(self):
        self._running = True
        logger.info(
            "Document worker started (poll=%ds, concurrency=%d, stale=%ds)",
            self._interval, self._max_concurrent, self._stale_timeout,
        )
        while self._running:
            try:
                await self._recover_stale_jobs()
                await self._poll_and_process()
            except Exception:
                logger.exception("Document worker cycle failed")
            await asyncio.sleep(self._interval)

    def stop(self):
        self._running = False

    async def _recover_stale_jobs(self):
        """Reset jobs stuck in 'processing' longer than the stale timeout back to 'pending'."""
        result = await self._pool.execute(
            "UPDATE documents SET status = 'pending', updated_at = now() "
            "WHERE status = 'processing' AND NOT archived "
            f"AND updated_at < now() - interval '{self._stale_timeout} seconds'"
        )
        if result and result != "UPDATE 0":
            logger.info("Recovered stale jobs: %s", result)

    async def _poll_and_process(self):
        """Claim and process one pending document if under concurrency limit."""
        if self._in_flight >= self._max_concurrent:
            return

        row = await self._pool.fetchrow(
            "UPDATE documents SET status = 'processing', updated_at = now() "
            "WHERE id = ("
            "  SELECT id FROM documents "
            "  WHERE status = 'pending' AND NOT archived "
            "  ORDER BY created_at "
            "  LIMIT 1 "
            "  FOR UPDATE SKIP LOCKED"
            ") RETURNING id::text, user_id::text, knowledge_base_id::text as kb_id, "
            "parser, url, filename, file_type"
        )
        if not row:
            return

        self._in_flight += 1
        asyncio.create_task(self._process_one(row))

    async def _process_one(self, row: dict):
        doc_id = row["id"]
        try:
            if row["parser"] == "confluence" and self._confluence and row["url"]:
                await self._confluence.import_page(
                    doc_id, row["user_id"], row["kb_id"], row["url"],
                )
            else:
                await self._ocr.process_document(doc_id, row["user_id"])
        except Exception:
            logger.exception("Worker failed for doc %s", doc_id[:8])
            try:
                await self._pool.execute(
                    "UPDATE documents SET status = 'failed', "
                    "error_message = 'Processing failed — see server logs', "
                    "updated_at = now() WHERE id = $1",
                    doc_id,
                )
            except Exception:
                logger.exception("Failed to mark doc %s as failed", doc_id[:8])
        finally:
            self._in_flight -= 1
