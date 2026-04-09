import asyncio
import json
import logging
import shutil
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

_BASE_DIR = Path(settings.S3_BUCKET if settings.S3_BUCKET.startswith("/") else "/data")


class LocalStorageService:
    """Drop-in replacement for S3Service that stores files on local disk."""

    def __init__(self, base_dir: str = str(_BASE_DIR), api_url: str = ""):
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        # URL that the *browser* uses to fetch files (not internal Docker URL)
        self._api_url = api_url or settings.APP_URL.replace(":3000", ":8000")

    async def upload_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream"):
        dest = self._base / key
        await asyncio.to_thread(self._write, dest, data)

    async def upload_file(self, key: str, file_path: str, content_type: str = "application/octet-stream"):
        dest = self._base / key
        await asyncio.to_thread(self._copy, file_path, dest)

    async def generate_presigned_get(self, key: str, expires_in: int = 3600) -> str:
        return f"{self._api_url}/files/{key}"

    async def generate_presigned_put(self, key: str, content_type: str = "application/pdf", expires_in: int = 3600) -> str:
        return f"{self._api_url}/files/{key}"

    async def download_bytes(self, key: str) -> bytes:
        return await asyncio.to_thread((self._base / key).read_bytes)

    async def download_to_file(self, key: str, file_path: str):
        await asyncio.to_thread(self._copy, self._base / key, file_path)

    async def download_json(self, key: str) -> dict:
        body = await self.download_bytes(key)
        return json.loads(body)

    @staticmethod
    def _write(dest: Path, data: bytes):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    @staticmethod
    def _copy(src, dest):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dest))


# Alias so existing imports like `from services.s3 import S3Service` keep working
S3Service = LocalStorageService
