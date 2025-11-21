from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional, Set

import aiofiles
import httpx
from loguru import logger

from tldw_Server_API.app.core.testing import is_test_mode
from tldw_Server_API.app.core.http_client import afetch as _m_afetch, adownload as _m_adownload, DEFAULT_MAX_REDIRECTS as _DEFAULT_MAX_REDIRECTS

async def download_url_async(
    client: Optional[httpx.AsyncClient],
    url: str,
    target_dir: Path,
    allowed_extensions: Optional[Set[str]] = None,
    check_extension: bool = True,
    disallow_content_types: Optional[Set[str]] = None,
    allow_redirects: bool = True,
) -> Path:
    """
    Minimal core-backed URL downloader used by tests and modular endpoints.

    Behaviour is aligned with the legacy implementation for the cases
    exercised in test_json_url_download:

    - When Content-Disposition specifies a filename, use that name.
    - Otherwise derive the name from the URL path.
    - If check_extension is True and allowed_extensions is non-empty,
      infer a suitable suffix from:
        * the path
        * or a small content-type map (including application/json)
      and error when the inferred extension is not allowed or when the
      content-type is explicitly disallowed.
    """
    if allowed_extensions is None:
        allowed_extensions = set()

    # Derive a seed filename from URL
    try:
        url_obj = httpx.URL(url)
        seed_segment = url_obj.path.split("/")[-1] or f"downloaded_{hash(url)}.tmp"
    except Exception:
        seed_segment = f"downloaded_{hash(url)}.tmp"

    test_mode_active = bool(is_test_mode()) or bool(__import__("os").getenv("PYTEST_CURRENT_TEST"))

    # When a client is provided, reuse the richer legacy-style logic so behaviour
    # matches `_legacy_media._download_url_async` (including offline stubs) in both
    # legacy-enabled and legacy-free modes.
    if client is not None:
        try:
            from tldw_Server_API.app.api.v1.endpoints._legacy_media import (  # type: ignore
                _download_url_async as _legacy_download,
            )
        except Exception:
            _legacy_download = None  # type: ignore[assignment]

        if _legacy_download is not None:
            return await _legacy_download(  # type: ignore[return-value]
                client=client,
                url=url,
                target_dir=target_dir,
                allowed_extensions=allowed_extensions,
                check_extension=check_extension,
                disallow_content_types=disallow_content_types,
                allow_redirects=allow_redirects,
            )

    # No client supplied (or legacy helper unavailable): create one and delegate
    # back into this helper so that tests which patch the media shim still see
    # consistent behaviour.
    owns_client = False
    if client is None:
        timeout = httpx.Timeout(60.0)
        client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)
        owns_client = True

    owns_client = False
    if client is None:
        timeout = httpx.Timeout(60.0)
        client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)
        owns_client = True

    try:
        async with client.stream(
            "GET",
            url,
            follow_redirects=allow_redirects,
            timeout=60.0,
        ) as resp:
            resp.raise_for_status()

            # Normalize content-type early and enforce disallow list regardless of extension.
            content_type = (
                resp.headers.get("content-type") or ""
            ).split(";", 1)[0].strip().lower()
            if disallow_content_types and content_type in disallow_content_types:
                allowed_list = ", ".join(sorted(allowed_extensions or [])) or "*"
                raise ValueError(
                    f"Downloaded file from {url} does not have an allowed extension "
                    f"(allowed: {allowed_list}); content-type '{content_type}' unsupported "
                    "for this endpoint"
                )

            # Determine filename from Content-Disposition when present.
            filename = seed_segment
            cd = resp.headers.get("content-disposition") or ""
            if "filename=" in cd:
                try:
                    # naive parse: filename="name.ext"
                    part = cd.split("filename=", 1)[1]
                    if part.startswith("\""):
                        part = part.split("\"", 2)[1]
                    else:
                        part = part.split(";", 1)[0]
                    part = part.strip()
                    if part:
                        filename = part
                except Exception:
                    pass

            # Basic sanitization
            safe_name = "".join(
                c if c.isalnum() or c in ("-", "_", ".") else "_"
                for c in filename
            ) or seed_segment

            # Determine effective suffix, checking allowed_extensions when requested.
            effective_suffix = Path(safe_name).suffix.lower()
            if check_extension and allowed_extensions:
                if not effective_suffix or effective_suffix not in allowed_extensions:
                    # Try inferring from final response URL path.
                    try:
                        alt_seg = resp.url.path.split("/")[-1]
                        alt_suffix = Path(alt_seg).suffix.lower()
                    except Exception:
                        alt_suffix = ""
                    if alt_suffix and alt_suffix in allowed_extensions:
                        effective_suffix = alt_suffix
                        base = Path(safe_name).stem
                        safe_name = f"{base}{effective_suffix}"
                    else:
                        # Fallback to content-type mapping (re-use normalized content_type).
                        content_type_map = {
                            "application/json": ".json",
                            "application/pdf": ".pdf",
                            "text/plain": ".txt",
                            "text/markdown": ".md",
                            "text/x-markdown": ".md",
                        }
                        mapped_ext = content_type_map.get(content_type)
                        if mapped_ext and mapped_ext in allowed_extensions:
                            effective_suffix = mapped_ext
                            base = Path(safe_name).stem
                            safe_name = f"{base}{effective_suffix}"
                        else:
                            allowed_list = ", ".join(sorted(allowed_extensions))
                            raise ValueError(
                                f"Downloaded file from {url} does not have an allowed extension "
                                f"(allowed: {allowed_list}); content-type '{content_type}' unsupported "
                                "for this endpoint"
                            )

            target_path = target_dir / safe_name
            counter = 1
            stem = target_path.stem
            suffix = target_path.suffix
            while target_path.exists():
                target_path = target_dir / f"{stem}_{counter}{suffix}"
                counter += 1

            target_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(target_path, "wb") as f:
                async for chunk in resp.aiter_bytes():
                    if chunk:
                        await f.write(chunk)

            logger.info("Downloaded %s to %s", url, target_path)
            return target_path
    finally:
        if owns_client:
            try:
                await client.aclose()
            except Exception:
                pass
