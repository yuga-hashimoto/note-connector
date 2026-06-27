"""Image materialization for ChatGPT-generated images."""

from __future__ import annotations

import base64
import re
import uuid
from pathlib import Path

import httpx

from note_mcp.api.images import validate_image_file

_MIME_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def normalize_mime_type(mime_type: str) -> str:
    """Normalize MIME type by stripping parameters."""
    return mime_type.split(";", maxsplit=1)[0].strip().lower()


def extension_for_mime(mime_type: str) -> str:
    """Return file extension for a supported image MIME type."""
    normalized = normalize_mime_type(mime_type)
    ext = _MIME_TO_EXT.get(normalized)
    if ext is None:
        raise ValueError(f"Unsupported image MIME type: {mime_type}")
    return ext


async def download_image_url(url: str, dest_path: Path) -> None:
    """Download image bytes from URL to dest_path."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        dest_path.write_bytes(response.content)


def write_base64_image(image_base64: str, dest_path: Path) -> None:
    """Decode base64 image data and write to dest_path."""
    cleaned = re.sub(r"\s+", "", image_base64)
    if cleaned.startswith("data:") and "," in cleaned:
        cleaned = cleaned.split(",", maxsplit=1)[1]
    raw = base64.b64decode(cleaned, validate=True)
    dest_path.write_bytes(raw)


def materialize_image_input_sync(
    work_dir: Path,
    *,
    image_base64: str | None,
    image_url: str | None,
    mime_type: str,
) -> Path:
    """Write image input to a temp file and validate it."""
    work_dir.mkdir(parents=True, exist_ok=True)
    ext = extension_for_mime(mime_type)
    dest = work_dir / f"chatgpt-{uuid.uuid4().hex}{ext}"
    if image_base64:
        write_base64_image(image_base64, dest)
    elif image_url:
        raise ValueError("image_url requires async materialize_image_input")
    else:
        raise ValueError("Provide image_base64 or image_url")
    validate_image_file(str(dest))
    return dest


async def materialize_image_input(
    work_dir: Path,
    *,
    image_base64: str | None,
    image_url: str | None,
    mime_type: str,
) -> Path:
    """Write image input to a temp file and validate it."""
    work_dir.mkdir(parents=True, exist_ok=True)
    ext = extension_for_mime(mime_type)
    dest = work_dir / f"chatgpt-{uuid.uuid4().hex}{ext}"
    if image_base64:
        write_base64_image(image_base64, dest)
    elif image_url:
        await download_image_url(image_url, dest)
    else:
        raise ValueError("Provide image_base64 or image_url")
    validate_image_file(str(dest))
    return dest
