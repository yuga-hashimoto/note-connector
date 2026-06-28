"""Tests for Apps SDK file-parameter eyecatch image handling."""

from __future__ import annotations

import hashlib
import io

import pytest
from PIL import Image as PILImage

from note_mcp.api.openai_file_images import (
    EYECATCH_RECOMMENDED_HEIGHT,
    EYECATCH_RECOMMENDED_WIDTH,
    ValidatedOpenAIImage,
    decode_image_dimensions,
    detect_image_type,
    normalize_eyecatch_image_if_needed,
)
from note_mcp.models import NoteAPIError


def make_png(width: int = 128, height: int = 67) -> bytes:
    output = io.BytesIO()
    PILImage.new("RGB", (width, height), color=(255, 255, 255)).save(output, format="PNG")
    return output.getvalue()


def test_detect_and_decode_png_dimensions() -> None:
    data = make_png(1280, 670)
    mime_type, suffix, image_format = detect_image_type(data)
    width, height = decode_image_dimensions(data, image_format)

    assert mime_type == "image/png"
    assert suffix == ".png"
    assert image_format == "PNG"
    assert (width, height) == (1280, 670)


def test_svg_rejected() -> None:
    with pytest.raises(NoteAPIError) as exc_info:
        detect_image_type(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>')

    assert "SVG" in exc_info.value.message


def test_normalize_to_note_recommended_size() -> None:
    original_data = make_png(800, 800)
    image = ValidatedOpenAIImage(
        data=original_data,
        sha256=hashlib.sha256(original_data).hexdigest(),
        mime_type="image/png",
        file_name="square.png",
        file_id="file_square",
        width=800,
        height=800,
        suffix=".png",
    )

    normalized = normalize_eyecatch_image_if_needed(image)

    assert normalized.normalized is True
    assert normalized.mime_type == "image/png"
    assert normalized.width == EYECATCH_RECOMMENDED_WIDTH
    assert normalized.height == EYECATCH_RECOMMENDED_HEIGHT
    assert normalized.sha256 == hashlib.sha256(normalized.data).hexdigest()
