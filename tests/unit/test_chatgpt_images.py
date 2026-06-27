"""Tests for ChatGPT image ingestion helpers."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from note_mcp.chatgpt.images import (
    extension_for_mime,
    materialize_image_input_sync,
    normalize_mime_type,
)


def test_normalize_mime_type_strips_parameters() -> None:
    assert normalize_mime_type("image/png; charset=binary") == "image/png"


def test_extension_for_mime() -> None:
    assert extension_for_mime("image/jpeg") == ".jpg"
    assert extension_for_mime("image/png") == ".png"


def test_materialize_image_from_base64(tmp_path: Path) -> None:
    raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    encoded = base64.b64encode(raw).decode("ascii")
    path = materialize_image_input_sync(
        tmp_path,
        image_base64=encoded,
        mime_type="image/png",
        image_url=None,
    )
    assert path.exists()
    assert path.read_bytes()[:8] == raw[:8]
    assert path.suffix == ".png"


def test_materialize_image_requires_one_source(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="image_base64 or image_url"):
        materialize_image_input_sync(
            tmp_path,
            image_base64=None,
            mime_type="image/png",
            image_url=None,
        )
