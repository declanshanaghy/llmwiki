"""Confluence page import service.

Fetches a Confluence page via REST API, transforms its XHTML storage format
into clean HTML, downloads and embeds images/diagrams as data URIs, then
hands off to the existing HTML processing pipeline.
"""

import asyncio
import base64
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from config import settings

logger = logging.getLogger(__name__)

_PAGE_ID_RE = re.compile(r"/pages/(?:edit-v2/)?(\d+)")
_PAGE_ID_QS_RE = re.compile(r"pageId=(\d+)")

_MAX_IMG_BYTES = 5 * 1024 * 1024     # 5 MB per image
_MAX_TOTAL_BYTES = 20 * 1024 * 1024  # 20 MB total
_CONCURRENT = 8


def _parse_page_id(url: str) -> str:
    m = _PAGE_ID_RE.search(url)
    if m:
        return m.group(1)
    m = _PAGE_ID_QS_RE.search(url)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot extract page ID from URL: {url}")


class ConfluenceService:
    def __init__(self, pool, s3, ocr_service):
        self._pool = pool
        self._s3 = s3
        self._ocr = ocr_service

    async def import_page(self, document_id: str, user_id: str, kb_id: str, page_url: str):
        """Main entry point — called by the document worker."""
        try:
            await self._pool.execute(
                "UPDATE documents SET status = 'processing', updated_at = now() WHERE id = $1",
                document_id,
            )

            page_id = _parse_page_id(page_url)
            base = settings.CONFLUENCE_BASE_URL.rstrip("/")
            auth = (settings.CONFLUENCE_EMAIL, settings.CONFLUENCE_API_TOKEN)

            async with httpx.AsyncClient(timeout=30) as client:
                # Fetch page first (need body for transform), then parallelize the rest
                page = await self._fetch_page(client, base, auth, page_id)
                attachments, children, ancestors = await asyncio.gather(
                    self._fetch_attachments(client, base, auth, page_id),
                    self._fetch_children(client, base, auth, page_id),
                    self._fetch_ancestors(client, base, auth, page_id),
                )
                clean_html = await self._transform(client, base, auth, page_id, page, attachments, children)

            # Build rich metadata from Confluence API response
            version = page.get("version", {})
            now_utc = datetime.now(timezone.utc).isoformat()
            rich_metadata = {
                "confluence_page_id": page_id,
                "confluence_space_id": page.get("spaceId", ""),
                "confluence_space_key": (page.get("_links", {}).get("webui", "").split("/spaces/")[1].split("/")[0]
                                         if "/spaces/" in page.get("_links", {}).get("webui", "") else ""),
                "confluence_parent_id": page.get("parentId", ""),
                "confluence_parent_type": page.get("parentType", ""),
                "confluence_version": version.get("number", 0),
                "confluence_version_date": version.get("createdAt", ""),
                "confluence_created_at": page.get("createdAt", ""),
                "confluence_author_id": page.get("authorId", ""),
                "confluence_position": page.get("position", 0),
                "confluence_webui": page.get("_links", {}).get("webui", ""),
                "confluence_ancestors": ancestors,
                "confluence_child_ids": [str(c["id"]) for c in children],
                "confluence_last_synced_at": now_utc,
            }

            await self._pool.execute(
                "UPDATE documents SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb, updated_at = now() WHERE id = $1",
                document_id, json.dumps(rich_metadata),
            )

            # Store as source.html — this IS the display artifact (viewer serves tagged.html)
            html_bytes = clean_html.encode("utf-8")
            s3_key = f"{user_id}/{document_id}/source.html"
            tagged_key = f"{user_id}/{document_id}/tagged.html"
            await self._s3.upload_bytes(s3_key, html_bytes, "text/html")
            # Serve the same clean HTML directly — no second parser pass
            await self._s3.upload_bytes(tagged_key, html_bytes, "text/html")

            # Update title from Confluence page title
            title = page.get("title", "")
            if title:
                await self._pool.execute(
                    "UPDATE documents SET title = $2, updated_at = now() WHERE id = $1",
                    document_id, title,
                )

            # Simple text extraction for search chunks — no heavy HTML parser
            from bs4 import BeautifulSoup as BS
            from services.chunker import chunk_text, store_chunks
            text = BS(clean_html, "html.parser").get_text(separator="\n", strip=True)
            chunks = chunk_text(text)
            await store_chunks(self._pool, document_id, user_id, kb_id, chunks)

            await self._pool.execute(
                "UPDATE documents SET status = 'ready', content = $2, file_type = 'html', "
                "page_count = 1, parser = 'confluence', updated_at = now() WHERE id = $1",
                document_id, text[:50000],
            )

            logger.info("Confluence import complete: doc=%s page_id=%s", document_id[:8], page_id)

        except Exception as e:
            logger.exception("Confluence import failed: doc=%s", document_id[:8])
            await self._pool.execute(
                "UPDATE documents SET status = 'failed', error_message = $2, updated_at = now() WHERE id = $1",
                document_id, str(e)[:500],
            )

    async def check_page_version(self, page_id: str) -> int | None:
        """Fetch only the current version number. Returns None on error."""
        base = settings.CONFLUENCE_BASE_URL.rstrip("/")
        auth = (settings.CONFLUENCE_EMAIL, settings.CONFLUENCE_API_TOKEN)
        api_base = base if base.endswith("/wiki") else base + "/wiki"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{api_base}/api/v2/pages/{page_id}", auth=auth)
                resp.raise_for_status()
                return resp.json().get("version", {}).get("number")
        except Exception as e:
            logger.warning("Version check failed for page %s: %s", page_id, e)
            return None

    async def fetch_space_pages(self, space_key: str) -> list[dict]:
        """Fetch all pages in a Confluence space via CQL. Returns list of {id, title, webui}."""
        base = settings.CONFLUENCE_BASE_URL.rstrip("/")
        auth = (settings.CONFLUENCE_EMAIL, settings.CONFLUENCE_API_TOKEN)
        api_base = base if base.endswith("/wiki") else base + "/wiki"
        pages = []
        start = 0
        limit = 50
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                cql = f'space="{space_key}" AND type=page ORDER BY title'
                resp = await client.get(
                    f"{api_base}/rest/api/content/search",
                    params={"cql": cql, "limit": limit, "start": start},
                    auth=auth,
                )
                resp.raise_for_status()
                data = resp.json()
                for r in data.get("results", []):
                    pages.append({
                        "id": str(r["id"]),
                        "title": r.get("title", ""),
                        "webui": r.get("_links", {}).get("webui", ""),
                    })
                if data.get("size", 0) < limit:
                    break
                start += limit
        return pages

    async def _fetch_page(self, client: httpx.AsyncClient, base: str, auth: tuple, page_id: str) -> dict:
        # base may already end with /wiki (e.g. https://x.atlassian.net/wiki)
        api_base = base.rstrip("/")
        if not api_base.endswith("/wiki"):
            api_base += "/wiki"
        url = f"{api_base}/api/v2/pages/{page_id}?body-format=storage"
        resp = await client.get(url, auth=auth)
        resp.raise_for_status()
        return resp.json()

    async def _fetch_attachments(self, client: httpx.AsyncClient, base: str, auth: tuple, page_id: str) -> list[dict]:
        api_base = base.rstrip("/")
        if not api_base.endswith("/wiki"):
            api_base += "/wiki"
        url = f"{api_base}/rest/api/content/{page_id}/child/attachment?limit=100"
        resp = await client.get(url, auth=auth)
        resp.raise_for_status()
        return resp.json().get("results", [])

    async def _fetch_children(self, client: httpx.AsyncClient, base: str, auth: tuple, page_id: str) -> list[dict]:
        api_base = base.rstrip("/")
        if not api_base.endswith("/wiki"):
            api_base += "/wiki"
        url = f"{api_base}/rest/api/content/{page_id}/child/page?limit=100"
        try:
            resp = await client.get(url, auth=auth)
            resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception as e:
            logger.warning("Failed to fetch child pages for %s: %s", page_id, e)
            return []

    async def _fetch_ancestors(self, client: httpx.AsyncClient, base: str, auth: tuple, page_id: str) -> list[dict]:
        api_base = base.rstrip("/")
        if not api_base.endswith("/wiki"):
            api_base += "/wiki"
        url = f"{api_base}/rest/api/content/{page_id}?expand=ancestors"
        try:
            resp = await client.get(url, auth=auth)
            resp.raise_for_status()
            return [{"id": str(a["id"]), "title": a["title"]} for a in resp.json().get("ancestors", [])]
        except Exception as e:
            logger.warning("Failed to fetch ancestors for %s: %s", page_id, e)
            return []

    async def _download_attachment(self, client: httpx.AsyncClient, base: str, auth: tuple, download_path: str) -> bytes | None:
        from urllib.parse import urlparse
        origin = f"{urlparse(base).scheme}://{urlparse(base).netloc}"
        # Confluence returns paths like /download/attachments/... but they live under /wiki/
        if not download_path.startswith("/wiki"):
            download_path = "/wiki" + download_path
        url = origin + download_path
        try:
            resp = await client.get(url, auth=auth, follow_redirects=True)
            resp.raise_for_status()
            data = resp.content
            if len(data) > _MAX_IMG_BYTES:
                logger.warning("Attachment too large (%d bytes), skipping: %s", len(data), download_path)
                return None
            return data
        except Exception as e:
            logger.warning("Failed to download attachment %s: %s", download_path, e)
            return None

    async def _transform(
        self,
        client: httpx.AsyncClient,
        base: str,
        auth: tuple,
        page_id: str,
        page: dict,
        attachments: list[dict],
        children: list[dict] | None = None,
    ) -> str:
        """Transform Confluence XHTML storage format into clean HTML with embedded images."""
        body = page.get("body", {}).get("storage", {}).get("value", "")
        if not body:
            return f"<h1>{page.get('title', 'Untitled')}</h1><p>Empty page</p>"

        soup = BeautifulSoup(body, "html.parser")

        # Build attachment lookup: filename -> download path
        att_map: dict[str, str] = {}
        for att in attachments:
            fname = att.get("title", "")
            dl = att.get("_links", {}).get("download", "")
            if fname and dl:
                att_map[fname] = dl

        total_bytes = 0
        sem = asyncio.Semaphore(_CONCURRENT)

        async def embed_attachment(filename: str) -> str:
            """Download an attachment and return data URI, or placeholder."""
            nonlocal total_bytes
            dl_path = att_map.get(filename)
            if not dl_path:
                return ""
            if total_bytes >= _MAX_TOTAL_BYTES:
                return ""
            async with sem:
                data = await self._download_attachment(client, base, auth, dl_path)
            if not data:
                return ""
            total_bytes += len(data)
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "gif": "image/gif", "svg": "image/svg+xml", "webp": "image/webp"}.get(ext, "image/png")
            b64 = base64.b64encode(data).decode()
            return f"data:{mime};base64,{b64}"

        # --- Process Confluence-specific elements ---

        # 1. <ac:image> with <ri:attachment>
        for ac_img in soup.find_all("ac:image"):
            ri = ac_img.find("ri:attachment")
            ri_url = ac_img.find("ri:url")
            if ri and ri.get("ri:filename"):
                data_uri = await embed_attachment(ri["ri:filename"])
                alt = ac_img.get("ac:alt", ri["ri:filename"])
                img_tag = soup.new_tag("img", src=data_uri or "#", alt=alt)
                ac_img.replace_with(img_tag)
            elif ri_url and ri_url.get("ri:value"):
                # External image URL — pass through for the parser
                img_tag = soup.new_tag("img", src=ri_url["ri:value"])
                ac_img.replace_with(img_tag)
            else:
                ac_img.decompose()

        # 2. Macros
        for macro in soup.find_all("ac:structured-macro"):
            name = macro.get("ac:name", "")

            if name == "drawio":
                # draw.io: look for auto-generated PNG preview
                diagram_name = ""
                for param in macro.find_all("ac:parameter"):
                    if param.get("ac:name") == "diagramName":
                        diagram_name = param.get_text(strip=True)
                preview_name = f"{diagram_name}.png" if diagram_name else None
                data_uri = ""
                if preview_name:
                    data_uri = await embed_attachment(preview_name)
                if not data_uri and diagram_name:
                    # Try with .drawio.png suffix
                    data_uri = await embed_attachment(f"{diagram_name}.drawio.png")
                if data_uri:
                    img_tag = soup.new_tag("img", src=data_uri, alt=f"draw.io: {diagram_name}")
                    macro.replace_with(img_tag)
                else:
                    macro.replace_with(f"[draw.io diagram: {diagram_name}]")

            elif name == "lucidchart":
                # Lucidchart: look for rendered image attachment
                doc_id = ""
                for param in macro.find_all("ac:parameter"):
                    if param.get("ac:name") == "documentId":
                        doc_id = param.get_text(strip=True)
                # Lucidchart stores images as attachments with "lucidchart" in the name
                found = False
                for fname, dl_path in att_map.items():
                    if "lucidchart" in fname.lower() or (doc_id and doc_id in fname):
                        data_uri = await embed_attachment(fname)
                        if data_uri:
                            img_tag = soup.new_tag("img", src=data_uri, alt=f"Lucidchart: {doc_id}")
                            macro.replace_with(img_tag)
                            found = True
                            break
                if not found:
                    macro.replace_with(f"[Lucidchart diagram: {doc_id}]")

            elif name in ("code", "noformat"):
                lang = ""
                for param in macro.find_all("ac:parameter"):
                    if param.get("ac:name") == "language":
                        lang = param.get_text(strip=True)
                body_tag = macro.find("ac:plain-text-body") or macro.find("ac:rich-text-body")
                code_text = body_tag.get_text() if body_tag else ""
                pre = soup.new_tag("pre")
                code = soup.new_tag("code")
                if lang:
                    code["class"] = f"language-{lang}"
                code.string = code_text
                pre.append(code)
                macro.replace_with(pre)

            elif name in ("info", "note", "warning", "tip"):
                label = name.capitalize()
                body_tag = macro.find("ac:rich-text-body")
                inner = body_tag.decode_contents() if body_tag else ""
                bq = soup.new_tag("blockquote")
                bq.append(BeautifulSoup(f"<strong>{label}:</strong> {inner}", "html.parser"))
                macro.replace_with(bq)

            elif name == "toc":
                macro.decompose()

            elif name in ("children", "pagetree", "pagetreesearch"):
                # Render child pages as a list of links
                if children:
                    from urllib.parse import urlparse
                    origin = f"{urlparse(base).scheme}://{urlparse(base).netloc}"
                    ul = soup.new_tag("ul")
                    for child in children:
                        title = child.get("title", "")
                        webui = child.get("_links", {}).get("webui", "")
                        href = f"{origin}/wiki{webui}" if webui else "#"
                        li = soup.new_tag("li")
                        a_tag = soup.new_tag("a", href=href)
                        a_tag.string = title
                        li.append(a_tag)
                        ul.append(li)
                    macro.replace_with(ul)
                else:
                    macro.replace_with("[Child pages]")

            elif name == "create-from-template":
                # Template instantiation buttons — render as descriptive text
                button_label = ""
                title_param = ""
                for param in macro.find_all("ac:parameter"):
                    pname = param.get("ac:name", "")
                    if pname == "buttonLabel":
                        button_label = param.get_text(strip=True)
                    elif pname == "title":
                        title_param = param.get_text(strip=True)
                label = button_label or title_param or "Template"
                span = soup.new_tag("span")
                span.string = label
                macro.replace_with(span)

            elif name == "status":
                # Status lozenges — render the title text
                status_text = ""
                for param in macro.find_all("ac:parameter"):
                    if param.get("ac:name") == "title":
                        status_text = param.get_text(strip=True)
                if status_text:
                    code = soup.new_tag("code")
                    code.string = status_text
                    macro.replace_with(code)
                else:
                    macro.decompose()

            elif name == "expand":
                body_tag = macro.find("ac:rich-text-body")
                if body_tag:
                    body_tag.unwrap()
                macro.unwrap()

            else:
                # Unknown macro — try to inline its body content
                body_tag = macro.find("ac:rich-text-body")
                if body_tag:
                    body_tag.unwrap()
                    macro.unwrap()
                else:
                    macro.decompose()

        # 3. Links to other Confluence pages — preserve as <a> tags
        for ac_link in soup.find_all("ac:link"):
            ri_page = ac_link.find("ri:page")
            ri_attachment = ac_link.find("ri:attachment")
            anchor = ac_link.get("ac:anchor", "")
            body = ac_link.find("ac:plain-text-link-body") or ac_link.find("ac:link-body")

            if ri_page:
                page_title = ri_page.get("ri:content-title", "")
                space_key = ri_page.get("ri:space-key", "")
                text = body.get_text(strip=True) if body else page_title
                # Build a Confluence URL so the link is clickable
                space_part = f"/spaces/{space_key}" if space_key else ""
                href = f"{base}/wiki{space_part}/pages?title={page_title}" if page_title else "#"
                a_tag = soup.new_tag("a", href=href, title=page_title)
                a_tag.string = text or page_title or "[link]"
                ac_link.replace_with(a_tag)
            elif ri_attachment:
                fname = ri_attachment.get("ri:filename", "")
                text = body.get_text(strip=True) if body else fname
                a_tag = soup.new_tag("a", href="#", title=f"Attachment: {fname}")
                a_tag.string = text or fname
                ac_link.replace_with(a_tag)
            elif anchor:
                text = body.get_text(strip=True) if body else anchor
                a_tag = soup.new_tag("a", href=f"#{anchor}")
                a_tag.string = text
                ac_link.replace_with(a_tag)
            else:
                if body:
                    body.unwrap()
                ac_link.unwrap()

        # 4. User mentions
        for user_tag in soup.find_all("ri:user"):
            parent = user_tag.parent
            username = user_tag.get("ri:username", user_tag.get("ri:userkey", "user"))
            mention = soup.new_tag("span")
            mention.string = f"@{username}"
            if parent and parent.name == "ac:link":
                parent.replace_with(mention)
            else:
                user_tag.replace_with(mention)

        # 5. Time/date elements — fill empty <time> tags with their datetime value
        for time_tag in soup.find_all("time"):
            if not time_tag.string and time_tag.get("datetime"):
                time_tag.string = time_tag["datetime"]

        # 6. Emoticons
        for emoticon in soup.find_all("ac:emoticon"):
            name = emoticon.get("ac:name", "")
            emoji_map = {
                "smile": "😊", "sad": "😢", "cheeky": "😜", "laugh": "😂",
                "wink": "😉", "thumbs-up": "👍", "thumbs-down": "👎",
                "information": "ℹ️", "tick": "✅", "cross": "❌",
                "warning": "⚠️", "plus": "➕", "minus": "➖",
                "question": "❓", "light-on": "💡", "light-off": "💡",
                "yellow-star": "⭐", "red-star": "⭐", "green-star": "⭐", "blue-star": "⭐",
                "heart": "❤️", "broken-heart": "💔",
            }
            emoticon.replace_with(emoji_map.get(name, f":{name}:"))

        # Wrap in a proper HTML document with the page title
        title = page.get("title", "Untitled")
        return f"<html><head><title>{title}</title></head><body><h1>{title}</h1>{soup}</body></html>"
