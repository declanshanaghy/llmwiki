import asyncio
import logging
from contextlib import asynccontextmanager

import asyncpg
import logfire
import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings

logger = logging.getLogger(__name__)

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        send_default_pii=True,
        traces_sample_rate=0.1,
        environment=settings.STAGE,
    )

if settings.LOGFIRE_TOKEN:
    logfire.configure(token=settings.LOGFIRE_TOKEN, service_name="supavault-api")
    logfire.instrument_asyncpg()

from routes.health import router as health_router
from routes.knowledge_bases import router as knowledge_bases_router
from routes.documents import router as documents_router
from routes.api_keys import router as api_keys_router
from routes.me import router as me_router
from routes.usage import router as usage_router
from routes.admin import router as admin_router
from infra.tus import router as tus_router, cleanup_stale_uploads
from routes.confluence import router as confluence_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=2, max_size=10)
    app.state.pool = pool

    from services.s3 import S3Service
    from services.ocr import OCRService
    from services.document_worker import DocumentWorker
    s3_service = S3Service()
    ocr_service = OCRService(s3_service, pool)

    app.state.s3_service = s3_service
    app.state.ocr_service = ocr_service

    confluence_service = None
    if settings.CONFLUENCE_BASE_URL:
        from services.confluence import ConfluenceService
        confluence_service = ConfluenceService(pool, s3_service, ocr_service)
    app.state.confluence_service = confluence_service

    cleanup_task = asyncio.create_task(cleanup_stale_uploads())

    # Generic document processing worker — replaces fire-and-forget pattern
    worker = DocumentWorker(pool, ocr_service, confluence_service)
    worker_task = asyncio.create_task(worker.start())

    # Confluence auto-sync
    sync_task = None
    if confluence_service and settings.CONFLUENCE_SYNC_ENABLED:
        from services.confluence_sync import ConfluenceSyncService
        sync_service = ConfluenceSyncService(pool, confluence_service)
        sync_task = asyncio.create_task(sync_service.start())

    yield

    worker.stop()
    worker_task.cancel()
    if sync_task:
        sync_task.cancel()
    cleanup_task.cancel()
    await pool.close()


app = FastAPI(title="Supavault API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.APP_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "Location", "Upload-Offset", "Upload-Length",
        "Tus-Resumable", "Tus-Version", "Tus-Max-Size", "Tus-Extension",
        "X-Document-Id",
    ],
)

if settings.LOGFIRE_TOKEN:
    logfire.instrument_fastapi(app)

app.include_router(health_router)
app.include_router(knowledge_bases_router)
app.include_router(documents_router)
app.include_router(api_keys_router)
app.include_router(me_router)
app.include_router(usage_router)
app.include_router(admin_router)
app.include_router(tus_router)
app.include_router(confluence_router)
