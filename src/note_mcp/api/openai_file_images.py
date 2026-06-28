"""OpenAI Apps SDK file-parameter image handling for note.com eyecatch uploads.

This module intentionally treats OpenAI file download URLs as secrets: they are
never logged, returned, or included in exception details.
"""

from __future__ import annotations

import hashlib
import io
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from PIL import Image as PILImage

from note_mcp.api.images import CONTENT_TYPE_MAP, MAX_FILE_SIZE, upload_eyecatch_image
from note_mcp.models import ErrorCode, Image, NoteAPIError, Session

logger = logging.getLogger(__name__)

EYECATCH_RECOMMENDED_WIDTH = 1280
EYECATCH_RECOMMENDED_HEIGHT = 670
EYECATCH_RECOMMENDED_RATIO = EYECATCH_RECOMMENDED_WIDTH / EYECATCH_RECOMMENDED_HEIGHT
EYECATCH_RATIO_TOLERANCE = 0.10
SENSITIVE_FILE_PARAM_KEYS: set[str] = {"download_url"}


@dataclass(frozen=True)
class ValidatedOpenAIImage:
    """Downloaded and validated OpenAI Apps SDK file parameter image."""

    data: bytes
    sha256: str
    mime_type: str
    file_name: str
    file_id: str
    width: int
    height: int
    suffix: str
    normalized: bool = False


def sanitize_file_param_for_details(image_file: dict[str, Any]) -> dict[str, Any]:
    """Return only non-sensitive file parameter fields for errors/logging."""
    return {
        key: value
        for key, value in image_file.items()
        if key not in SENSITIVE_FILE_PARAM_KEYS and isinstance(value, str | int | float | bool | type(None))
    }


def detect_image_type(data: bytes) -> tuple[str, str, str]:
    """Detect image type using magic bytes.

    Returns:
        Tuple of MIME type, file suffix, and Pillow format name.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png", "PNG"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg", "JPEG"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif", ".gif", "GIF"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp", "WEBP"
    if data.lstrip().lower().startswith(b"<svg") or b"<svg" in data[:512].lower():
        raise NoteAPIError(
            code=ErrorCode.INVALID_INPUT,
            message="SVG images are not allowed for eyecatch uploads.",
            details={"allowed_mime_types": sorted(set(CONTENT_TYPE_MAP.values()))},
        )
    raise NoteAPIError(
        code=ErrorCode.INVALID_INPUT,
        message="Unsupported or invalid image format. Allowed formats: JPEG, PNG, GIF, WebP.",
        details={"allowed_mime_types": sorted(set(CONTENT_TYPE_MAP.values()))},
    )


def decode_image_dimensions(data: bytes, expected_format: str) -> tuple[int, int]:
    """Decode image bytes with Pillow and return dimensions."""
    try:
        with PILImage.open(io.BytesIO(data)) as image:
            image.verify()
        with PILImage.open(io.BytesIO(data)) as image:
            actual_format = image.format or ""
            if actual_format.upper() != expected_format.upper():
                raise NoteAPIError(
                    code=ErrorCode.INVALID_INPUT,
                    message="Image magic bytes and decoded image format do not match.",
                    details={"decoded_format": actual_format, "expected_format": expected_format},
                )
            return int(image.width), int(image.height)
    except NoteAPIError:
        raise
    except Exception as exc:
        raise NoteAPIError(
            code=ErrorCode.INVALID_INPUT,
            message="Image decode failed. The file may be corrupt or unsupported.",
            details={"error_type": type(exc).__name__},
        ) from exc


def normalize_eyecatch_image_if_needed(image: ValidatedOpenAIImage) -> ValidatedOpenAIImage:
    """Resize/convert images that are not close to note's eyecatch recommendation.

    Animated GIFs are left unchanged to preserve animation. Other formats are
    converted to PNG only when the aspect ratio is far from 1280:670 or the
    dimensions exceed the recommended size.
    """
    ratio = image.width / image.height if image.height else 0
    ratio_delta = abs(ratio - EYECATCH_RECOMMENDED_RATIO) / EYECATCH_RECOMMENDED_RATIO
    should_resize = image.mime_type != "image/gif" and (
        ratio_delta > EYECATCH_RATIO_TOLERANCE
        or image.width > EYECATCH_RECOMMENDED_WIDTH
        or image.height > EYECATCH_RECOMMENDED_HEIGHT
    )
    if not should_resize:
        return image

    with PILImage.open(io.BytesIO(image.data)) as opened:
        source = opened.convert("RGBA")
        src_w, src_h = source.size
        target_ratio = EYECATCH_RECOMMENDED_RATIO
        src_ratio = src_w / src_h

        if src_ratio > target_ratio:
            crop_w = int(src_h * target_ratio)
            crop_h = src_h
            left = max((src_w - crop_w) // 2, 0)
            top = 0
        else:
            crop_w = src_w
            crop_h = int(src_w / target_ratio)
            left = 0
            top = max((src_h - crop_h) // 2, 0)

        cropped = source.crop((left, top, left + crop_w, top + crop_h))
        resampling = getattr(PILImage, "Resampling", PILImage).LANCZOS
        resized = cropped.resize((EYECATCH_RECOMMENDED_WIDTH, EYECATCH_RECOMMENDED_HEIGHT), resampling)

        output = io.BytesIO()
        resized.save(output, format="PNG", optimize=True)
        normalized_data = output.getvalue()

    if len(normalized_data) > MAX_FILE_SIZE:
        raise NoteAPIError(
            code=ErrorCode.INVALID_INPUT,
            message="Normalized eyecatch image exceeds maximum allowed size.",
            details={"size": len(normalized_data), "max_size": MAX_FILE_SIZE},
        )

    return ValidatedOpenAIImage(
        data=normalized_data,
        sha256=hashlib.sha256(normalized_data).hexdigest(),
        mime_type="image/png",
        file_name=Path(image.file_name).with_suffix(".png").name,
        file_id=image.file_id,
        width=EYECATCH_RECOMMENDED_WIDTH,
        height=EYECATCH_RECOMMENDED_HEIGHT,
        suffix=".png",
        normalized=True,
    )


async def download_and_validate_openai_image_file(
    image_file: dict[str, Any],
    *,
    max_size: int = MAX_FILE_SIZE,
) -> ValidatedOpenAIImage:
    """Download and validate an OpenAI Apps SDK file parameter image.

    The download_url is intentionally never included in errors or logs.
    """
    if not isinstance(image_file, dict):
        raise NoteAPIError(
            code=ErrorCode.INVALID_INPUT,
            message="image_file must be an object supplied by the Apps SDK file parameter mechanism.",
        )

    download_url = image_file.get("download_url")
    file_id = image_file.get("file_id")
    if not isinstance(download_url, str) or not download_url:
        raise NoteAPIError(
            code=ErrorCode.INVALID_INPUT,
            message="image_file.download_url is required.",
            details=sanitize_file_param_for_details(image_file),
        )
    if not isinstance(file_id, str) or not file_id:
        raise NoteAPIError(
            code=ErrorCode.INVALID_INPUT,
            message="image_file.file_id is required.",
            details=sanitize_file_param_for_details(image_file),
        )

    file_name_raw = image_file.get("file_name")
    file_name = str(file_name_raw) if file_name_raw else f"{file_id}.img"

    try:
        async with (
            httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client,
            client.stream(
                "GET",
                download_url,
                follow_redirects=True,
            ) as response,
        ):
            if response.status_code != 200:
                raise NoteAPIError(
                    code=ErrorCode.API_ERROR,
                    message=f"Failed to fetch image file: HTTP {response.status_code}.",
                    details={"status_code": response.status_code, "file_id": file_id, "file_name": file_name},
                )

            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_size:
                    raise NoteAPIError(
                        code=ErrorCode.INVALID_INPUT,
                        message="Image file exceeds maximum allowed size.",
                        details={"size": total, "max_size": max_size, "file_id": file_id, "file_name": file_name},
                    )
                chunks.append(chunk)
            data = b"".join(chunks)
    except NoteAPIError:
        raise
    except Exception as exc:
        raise NoteAPIError(
            code=ErrorCode.API_ERROR,
            message="Failed to fetch image file from the Apps SDK file reference.",
            details={"file_id": file_id, "file_name": file_name, "error_type": type(exc).__name__},
        ) from exc

    if not data:
        raise NoteAPIError(
            code=ErrorCode.INVALID_INPUT,
            message="Downloaded image file is empty.",
            details={"file_id": file_id, "file_name": file_name},
        )

    mime_type, suffix, image_format = detect_image_type(data)
    width, height = decode_image_dimensions(data, image_format)

    validated = ValidatedOpenAIImage(
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        mime_type=mime_type,
        file_name=Path(file_name).with_suffix(suffix).name,
        file_id=file_id,
        width=width,
        height=height,
        suffix=suffix,
        normalized=False,
    )
    return normalize_eyecatch_image_if_needed(validated)


async def upload_eyecatch_image_bytes(
    session: Session,
    image: ValidatedOpenAIImage,
    note_id: str,
) -> Image:
    """Upload an already validated image byte payload as an eyecatch image."""
    with tempfile.NamedTemporaryFile(prefix="note-eyecatch-", suffix=image.suffix, delete=True) as temp_file:
        temp_file.write(image.data)
        temp_file.flush()
        return await upload_eyecatch_image(session, temp_file.name, note_id=note_id)


async def resolve_article_url(session: Session, note_id: str) -> str | None:
    """Resolve a note URL without guessing sensitive/private data."""
    if note_id.startswith("n"):
        return f"https://note.com/{session.username}/n/{note_id}"

    if not note_id.isdigit():
        return None

    from note_mcp.api.articles import list_articles

    for page in range(1, 21):
        result = await list_articles(session, status=None, page=page, limit=10)
        for article in result.articles:
            if article.id == note_id:
                return article.url or f"https://note.com/{session.username}/n/{article.key}"
        if not result.has_more:
            break
    return None


async def set_eyecatch_from_openai_file_param(
    session: Session,
    note_id: str,
    image_file: dict[str, Any],
) -> dict[str, Any]:
    """Fetch an Apps SDK image file reference and set it as a note eyecatch."""
    validated = await download_and_validate_openai_image_file(image_file)
    uploaded = await upload_eyecatch_image_bytes(session, validated, note_id=note_id)
    article_url = await resolve_article_url(session, note_id)

    result = {
        "ok": True,
        "data": {
            "note_id": note_id,
            "article_url": article_url,
            "eyecatch_url": uploaded.url,
            "file_id": validated.file_id,
            "file_name": validated.file_name,
            "bytes": len(validated.data),
            "sha256": validated.sha256,
            "mime_type": validated.mime_type,
            "width": validated.width,
            "height": validated.height,
            "source": "openai_file_param",
        },
    }

    logger.info(
        "note eyecatch file-param upload: note_id=%s file_id=%s bytes=%s "
        "sha256=%s mime_type=%s width=%s height=%s result=ok",
        note_id,
        validated.file_id,
        len(validated.data),
        validated.sha256,
        validated.mime_type,
        validated.width,
        validated.height,
    )
    return result


async def download_and_validate_file_param_image_body(
    image_file: dict[str, Any],
    *,
    max_size: int = MAX_FILE_SIZE,
) -> ValidatedOpenAIImage:
    """Download and validate a file-parameter image for body insertion.

    Unlike eyecatch images, body images are NOT resized or converted.
    Original format, dimensions, and aspect ratio are preserved.
    """
    if not isinstance(image_file, dict):
        raise NoteAPIError(
            code=ErrorCode.INVALID_INPUT,
            message="image_file must be an object supplied by the Apps SDK file parameter mechanism.",
        )

    download_url = image_file.get("download_url")
    file_id = image_file.get("file_id")
    if not isinstance(download_url, str) or not download_url:
        raise NoteAPIError(
            code=ErrorCode.INVALID_INPUT,
            message="image_file.download_url is required.",
            details=sanitize_file_param_for_details(image_file),
        )
    if not isinstance(file_id, str) or not file_id:
        raise NoteAPIError(
            code=ErrorCode.INVALID_INPUT,
            message="image_file.file_id is required.",
            details=sanitize_file_param_for_details(image_file),
        )

    file_name_raw = image_file.get("file_name")
    file_name = str(file_name_raw) if file_name_raw else f"{file_id}.img"

    try:
        async with (
            httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client,
            client.stream(
                "GET",
                download_url,
                follow_redirects=True,
            ) as response,
        ):
            if response.status_code != 200:
                raise NoteAPIError(
                    code=ErrorCode.API_ERROR,
                    message=f"Failed to fetch image file: HTTP {response.status_code}.",
                    details={"status_code": response.status_code, "file_id": file_id, "file_name": file_name},
                )

            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_size:
                    raise NoteAPIError(
                        code=ErrorCode.INVALID_INPUT,
                        message="Image file exceeds maximum allowed size.",
                        details={"size": total, "max_size": max_size, "file_id": file_id, "file_name": file_name},
                    )
                chunks.append(chunk)
            data = b"".join(chunks)
    except NoteAPIError:
        raise
    except Exception as exc:
        raise NoteAPIError(
            code=ErrorCode.API_ERROR,
            message="Failed to fetch image file from the Apps SDK file reference.",
            details={"file_id": file_id, "file_name": file_name, "error_type": type(exc).__name__},
        ) from exc

    if not data:
        raise NoteAPIError(
            code=ErrorCode.INVALID_INPUT,
            message="Downloaded image file is empty.",
            details={"file_id": file_id, "file_name": file_name},
        )

    mime_type, suffix, image_format = detect_image_type(data)
    width, height = decode_image_dimensions(data, image_format)

    validated = ValidatedOpenAIImage(
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        mime_type=mime_type,
        file_name=Path(file_name).with_suffix(suffix).name,
        file_id=file_id,
        width=width,
        height=height,
        suffix=suffix,
        normalized=False,
    )

    should_convert_animated_gif = mime_type == "image/gif" and not _is_animated_gif(data)
    if should_convert_animated_gif:
        with PILImage.open(io.BytesIO(data)) as opened:
            buf = io.BytesIO()
            opened.save(buf, format="PNG", optimize=True)
            png_data = buf.getvalue()
        if len(png_data) > MAX_FILE_SIZE:
            raise NoteAPIError(
                code=ErrorCode.INVALID_INPUT,
                message="Converted image exceeds maximum allowed size.",
                details={"size": len(png_data), "max_size": MAX_FILE_SIZE},
            )
        validated = ValidatedOpenAIImage(
            data=png_data,
            sha256=hashlib.sha256(png_data).hexdigest(),
            mime_type="image/png",
            file_name=Path(validated.file_name).with_suffix(".png").name,
            file_id=validated.file_id,
            width=validated.width,
            height=validated.height,
            suffix=".png",
            normalized=True,
        )

    return validated


def _is_animated_gif(data: bytes) -> bool:
    """Check whether GIF data is animated (multiple frames)."""
    try:
        with PILImage.open(io.BytesIO(data)) as img:
            if hasattr(img, "n_frames") and img.n_frames > 1:
                return True
            if hasattr(img, "is_animated") and img.is_animated:
                return True
    except Exception:
        pass
    return False


async def insert_body_image_from_file_param(
    session: Session,
    article_id: str,
    image_file: dict[str, Any],
    caption: str | None = None,
) -> dict[str, Any]:
    """Download file-param image and insert into article body via API."""
    validated = await download_and_validate_file_param_image_body(image_file)

    with tempfile.NamedTemporaryFile(prefix="note-body-", suffix=validated.suffix, delete=True) as temp_file:
        temp_file.write(validated.data)
        temp_file.flush()

        from note_mcp.api.images import insert_image_via_api

        result = await insert_image_via_api(
            session=session,
            article_id=article_id,
            file_path=temp_file.name,
            caption=caption,
        )

    result["source"] = "openai_file_param"
    result["file_id"] = validated.file_id
    result["file_name"] = validated.file_name
    result["bytes"] = len(validated.data)
    result["sha256"] = validated.sha256
    result["mime_type"] = validated.mime_type
    result["width"] = validated.width
    result["height"] = validated.height

    logger.info(
        "note body image file-param insert: article_id=%s file_id=%s bytes=%s mime_type=%s result=ok",
        article_id,
        validated.file_id,
        len(validated.data),
        validated.mime_type,
    )
    return result
