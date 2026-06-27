"""Unit tests for base64 eyecatch image upload."""

from __future__ import annotations

import base64
import struct
import time
import zlib
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from note_mcp.api.images import (
    _decode_base64_image,
    _extract_image_url_from_response,
    _strip_data_url_prefix,
    _validate_image_bytes,
    _validate_mime_type,
    upload_eyecatch_chunked,
)
from note_mcp.models import ErrorCode, NoteAPIError, Session

if TYPE_CHECKING:
    pass


def _create_test_png_bytes(width: int = 10, height: int = 10) -> bytes:
    """Create minimal valid PNG bytes for testing."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr_chunk = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    raw_data = b""
    for _ in range(height):
        raw_data += b"\x00"
        for _ in range(width):
            raw_data += b"\xff\x00\x00"
    compressed = zlib.compress(raw_data, 9)
    idat_crc = zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF
    idat_chunk = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", idat_crc)
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    return signature + ihdr_chunk + idat_chunk + iend_chunk


def _create_test_jpeg_bytes() -> bytes:
    """Create minimal valid JPEG bytes for testing."""
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00\x43\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\x09\x09"
        b"\x08\x0a\x0c\x14\x0d\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f"
        b"\x1e\x1d\x1a\x1c\x1c\x20\x24\x2e\x27\x20\x22\x2c\x23\x1c\x1c\x28\x37"
        b"\x29\x2c\x30\x31\x34\x34\x34\x1f\x27\x39\x3d\x38\x32\x3c\x2e\x33\x34"
        b"\x32\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00"
        b"\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\xff\xc4\x00\xb5\x10\x00"
        b"\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01\x7d\x01\x02"
        b"\x03\x00\x04\x11\x05\x12\x21\x31\x41\x06\x13\x51\x61\x07\x22\x71\x14"
        b"\x32\x81\x91\xa1\x08\x23\x42\xb1\xc1\x15\x52\xd1\xf0\x24\x33\x62\x72"
        b"\x82\x09\x0a\x16\x17\x18\x19\x1a\x25\x26\x27\x28\x29\x2a\x34\x35\x36"
        b"\x37\x38\x39\x3a\x43\x44\x45\x46\x47\x48\x49\x4a\x53\x54\x55\x56\x57"
        b"\x58\x59\x5a\x63\x64\x65\x66\x67\x68\x69\x6a\x73\x74\x75\x76\x77\x78"
        b"\x79\x7a\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98"
        b"\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7"
        b"\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6"
        b"\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3"
        b"\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03"
        b"\x11\x00\x3f\x00\xa0\x78\x01\x40\x05\x00\x14\x00\x50\x01\x40\x05\x00"
        b"\x14\x01\xff\xd9"
    )


def _create_test_gif_bytes() -> bytes:
    """Create minimal valid GIF bytes for testing."""
    header = b"GIF89a"
    lsd = struct.pack("<HHBBB", 1, 1, 0, 0, 0)
    return header + lsd + b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"


def _create_mock_session() -> Session:
    """Create a mock session for testing."""
    return Session(
        cookies={"note_gql_auth_token": "token123", "_note_session_v5": "session456"},
        user_id="user123",
        username="testuser",
        expires_at=int(time.time()) + 3600,
        created_at=int(time.time()),
    )


# =============================================================================
# _strip_data_url_prefix
# =============================================================================


class TestStripDataUrlPrefix:
    """Tests for _strip_data_url_prefix."""

    def test_plain_base64(self) -> None:
        """Plain base64 should be returned unchanged."""
        result = _strip_data_url_prefix("iVBORw0KGgoAAAANSUhEUg==")
        assert result == "iVBORw0KGgoAAAANSUhEUg=="

    def test_data_url_png(self) -> None:
        """data:image/png;base64,... prefix should be stripped."""
        result = _strip_data_url_prefix("data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==")
        assert result == "iVBORw0KGgoAAAANSUhEUg=="

    def test_data_url_jpeg(self) -> None:
        """data:image/jpeg;base64,... prefix should be stripped."""
        result = _strip_data_url_prefix("data:image/jpeg;base64,/9j/4AAQSkZJRg==")
        assert result == "/9j/4AAQSkZJRg=="

    def test_data_url_with_charset(self) -> None:
        """data URL with charset parameter should be handled."""
        result = _strip_data_url_prefix("data:image/png;charset=utf-8;base64,abc123")
        assert result == "abc123"

    def test_empty_string(self) -> None:
        """Empty string should be returned empty."""
        result = _strip_data_url_prefix("")
        assert result == ""


# =============================================================================
# _decode_base64_image
# =============================================================================


class TestDecodeBase64Image:
    """Tests for _decode_base64_image."""

    def test_valid_png_base64(self) -> None:
        """Valid PNG base64 should decode successfully."""
        raw = _create_test_png_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        result = _decode_base64_image(b64)
        assert result == raw

    def test_valid_data_url(self) -> None:
        """Data URL format should be handled."""
        raw = _create_test_png_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        result = _decode_base64_image(f"data:image/png;base64,{b64}")
        assert result == raw

    def test_empty_base64(self) -> None:
        """Empty base64 should raise INVALID_BASE64."""
        with pytest.raises(NoteAPIError) as exc_info:
            _decode_base64_image("")
        assert exc_info.value.code == ErrorCode.INVALID_BASE64

    def test_whitespace_only(self) -> None:
        """Whitespace-only base64 should raise INVALID_BASE64."""
        with pytest.raises(NoteAPIError) as exc_info:
            _decode_base64_image("   \n\t  ")
        assert exc_info.value.code == ErrorCode.INVALID_BASE64

    def test_invalid_base64(self) -> None:
        """Strings with non-base64 characters decode to garbage -> INVALID_IMAGE downstream."""
        raw = b"!!!invalid!!!" + b"\x00" * 10
        b64 = base64.b64encode(raw).decode("ascii")
        # Mess up the base64 so it decodes to garbage
        messed = b64[:-4] + "!!!!"
        result = _decode_base64_image(messed)
        # Decode may succeed with validate=False, but result is garbage bytes
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_truly_invalid_base64(self) -> None:
        """Base64 with embedded null bytes should fail."""
        with pytest.raises(NoteAPIError) as exc_info:
            _decode_base64_image("abc\x00def")
        assert exc_info.value.code == ErrorCode.INVALID_BASE64

    def test_missing_padding(self) -> None:
        """Base64 with missing padding (common ChatGPT issue) should auto-fix."""
        raw = _create_test_png_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        stripped = b64.rstrip("=")
        # Verify decode works even without padding
        result = _decode_base64_image(stripped)
        assert result == raw

    def test_missing_padding_extra_char(self) -> None:
        """Base64 with truncated chars (forces padding mismatch) should still work."""
        raw = _create_test_png_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        # Strip padding first, then remove 1 more char to force non-multiple-of-4
        no_pad = b64.rstrip("=")
        stripped = no_pad[:-1]
        assert len(stripped) % 4 != 0, f"Expected non-multiple-of-4 length, got {len(stripped)}"
        result = _decode_base64_image(stripped)
        # Data should be valid bytes (last partial byte is reconstructed with padding)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_missing_padding_with_data_url(self) -> None:
        """Data URL with missing padding should still work."""
        raw = _create_test_png_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        stripped = b64.rstrip("=")
        result = _decode_base64_image(f"data:image/png;base64,{stripped}")
        assert result == raw

    def test_data_url_only_prefix(self) -> None:
        """Data URL with only prefix and no data should raise INVALID_BASE64."""
        with pytest.raises(NoteAPIError) as exc_info:
            _decode_base64_image("data:image/png;base64,")
        assert exc_info.value.code == ErrorCode.INVALID_BASE64


# =============================================================================
# _validate_mime_type
# =============================================================================


class TestValidateMimeType:
    """Tests for _validate_mime_type."""

    def test_png_supported(self) -> None:
        """image/png should be supported."""
        _validate_mime_type("image/png")

    def test_jpeg_supported(self) -> None:
        """image/jpeg should be supported."""
        _validate_mime_type("image/jpeg")

    def test_webp_supported(self) -> None:
        """image/webp should be supported."""
        _validate_mime_type("image/webp")

    def test_gif_supported(self) -> None:
        """image/gif should be supported."""
        _validate_mime_type("image/gif")

    def test_bmp_unsupported(self) -> None:
        """image/bmp should be rejected."""
        with pytest.raises(NoteAPIError) as exc_info:
            _validate_mime_type("image/bmp")
        assert exc_info.value.code == ErrorCode.UNSUPPORTED_MIME_TYPE

    def test_svg_unsupported(self) -> None:
        """image/svg+xml should be rejected."""
        with pytest.raises(NoteAPIError) as exc_info:
            _validate_mime_type("image/svg+xml")
        assert exc_info.value.code == ErrorCode.UNSUPPORTED_MIME_TYPE

    def test_empty_mime_type(self) -> None:
        """Empty MIME type should be rejected."""
        with pytest.raises(NoteAPIError) as exc_info:
            _validate_mime_type("")
        assert exc_info.value.code == ErrorCode.UNSUPPORTED_MIME_TYPE


# =============================================================================
# _extract_image_url_from_response
# =============================================================================


class TestExtractImageUrlFromResponse:
    """Tests for _extract_image_url_from_response."""

    def test_extract_url_field(self) -> None:
        """Standard 'url' field in data."""
        result = _extract_image_url_from_response({"data": {"url": "https://example.com/img.png"}})
        assert result == "https://example.com/img.png"

    def test_extract_image_url_field(self) -> None:
        """'image_url' field in data."""
        result = _extract_image_url_from_response({"data": {"image_url": "https://example.com/img.png"}})
        assert result == "https://example.com/img.png"

    def test_extract_src_field(self) -> None:
        """'src' field in data."""
        result = _extract_image_url_from_response({"data": {"src": "https://example.com/img.png"}})
        assert result == "https://example.com/img.png"

    def test_extract_download_url_field(self) -> None:
        """'download_url' field in data."""
        result = _extract_image_url_from_response({"data": {"download_url": "https://example.com/img.png"}})
        assert result == "https://example.com/img.png"

    def test_extract_note_image_url_field(self) -> None:
        """'note_image_url' field in data."""
        result = _extract_image_url_from_response({"data": {"note_image_url": "https://example.com/img.png"}})
        assert result == "https://example.com/img.png"

    def test_no_url_returns_none(self) -> None:
        """Response without any URL field returns None."""
        result = _extract_image_url_from_response({"data": {"status": "ok"}})
        assert result is None

    def test_empty_data_returns_none(self) -> None:
        """Empty data dict returns None."""
        result = _extract_image_url_from_response({"data": {}})
        assert result is None

    def test_no_data_key_returns_none(self) -> None:
        """Response without 'data' key returns None."""
        result = _extract_image_url_from_response({"status": "ok"})
        assert result is None

    def test_top_level_url(self) -> None:
        """URL at top level of response (fallback)."""
        result = _extract_image_url_from_response({"url": "https://example.com/img.png", "data": {}})
        assert result == "https://example.com/img.png"

    def test_empty_url_not_returned(self) -> None:
        """Empty string URL should not be returned."""
        result = _extract_image_url_from_response({"data": {"url": ""}})
        assert result is None

    def test_whitespace_url_not_returned(self) -> None:
        """Whitespace-only URL should not be returned."""
        result = _extract_image_url_from_response({"data": {"url": "   "}})
        assert result is None

    def test_url_priority_data_over_top(self) -> None:
        """URL in data takes priority over top-level."""
        result = _extract_image_url_from_response(
            {
                "data": {"url": "https://example.com/data.png"},
                "url": "https://example.com/top.png",
            }
        )
        assert result == "https://example.com/data.png"


# =============================================================================
# _validate_image_bytes
# =============================================================================


class TestValidateImageBytes:
    """Tests for _validate_image_bytes."""

    def test_valid_png(self) -> None:
        """Valid PNG bytes should pass validation."""
        raw = _create_test_png_bytes()
        _validate_image_bytes(raw, "image/png")

    def test_valid_jpeg(self) -> None:
        """Valid JPEG bytes should pass validation."""
        raw = _create_test_jpeg_bytes()
        _validate_image_bytes(raw, "image/jpeg")

    def test_valid_gif(self) -> None:
        """Valid GIF bytes should pass validation."""
        raw = _create_test_gif_bytes()
        _validate_image_bytes(raw, "image/gif")

    def test_empty_bytes(self) -> None:
        """Empty bytes should raise INVALID_IMAGE."""
        with pytest.raises(NoteAPIError) as exc_info:
            _validate_image_bytes(b"", "image/png")
        assert exc_info.value.code == ErrorCode.INVALID_IMAGE

    def test_wrong_magic_png_as_jpeg(self) -> None:
        """PNG bytes declared as JPEG should be rejected."""
        raw = _create_test_png_bytes()
        with pytest.raises(NoteAPIError) as exc_info:
            _validate_image_bytes(raw, "image/jpeg")
        assert exc_info.value.code == ErrorCode.INVALID_IMAGE

    def test_wrong_magic_jpeg_as_png(self) -> None:
        """JPEG bytes declared as PNG should be rejected."""
        raw = _create_test_jpeg_bytes()
        with pytest.raises(NoteAPIError) as exc_info:
            _validate_image_bytes(raw, "image/png")
        assert exc_info.value.code == ErrorCode.INVALID_IMAGE

    def test_random_bytes(self) -> None:
        """Random garbage bytes should be rejected."""
        with pytest.raises(NoteAPIError) as exc_info:
            _validate_image_bytes(b"not an image at all", "image/png")
        assert exc_info.value.code == ErrorCode.INVALID_IMAGE

    def test_too_short(self) -> None:
        """Bytes too short for magic check should be rejected."""
        with pytest.raises(NoteAPIError) as exc_info:
            _validate_image_bytes(b"\x89PN", "image/png")
        assert exc_info.value.code == ErrorCode.INVALID_IMAGE

    def test_webp_too_short(self) -> None:
        """Bytes too short for WebP magic check should be rejected."""
        with pytest.raises(NoteAPIError) as exc_info:
            _validate_image_bytes(b"RIFFab", "image/webp")
        assert exc_info.value.code == ErrorCode.INVALID_IMAGE

    def test_size_too_large(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Bytes exceeding MAX_FILE_SIZE should raise IMAGE_TOO_LARGE."""
        from note_mcp.api import images

        monkeypatch.setattr(images, "MAX_FILE_SIZE", 100)
        large_data = b"\x89PNG\r\n\x1a\n" + b"x" * 200
        with pytest.raises(NoteAPIError) as exc_info:
            _validate_image_bytes(large_data, "image/png")
        assert exc_info.value.code == ErrorCode.IMAGE_TOO_LARGE

    def test_valid_webp(self) -> None:
        """Valid WebP-like bytes should pass validation."""
        riif_header = b"RIFF\x00\x00\x00\x00WEBP"
        _validate_image_bytes(riif_header + b"x" * 50, "image/webp")


# =============================================================================
# upload_eyecatch_base64
# upload_eyecatch_chunked
# =============================================================================


class TestUploadEyecatchChunked:
    """Tests for upload_eyecatch_chunked function."""

    @pytest.fixture(autouse=True)
    def _clean_chunk_buffer(self) -> None:
        """Clean up chunk buffer before each test."""
        import note_mcp.api.images as img_mod

        img_mod._chunk_buffer.clear()

    @pytest.mark.asyncio
    async def test_single_chunk(self) -> None:
        """Single chunk upload should succeed."""
        from note_mcp.models import Image, ImageType

        session = _create_mock_session()
        raw = _create_test_png_bytes()
        b64 = base64.b64encode(raw).decode("ascii")

        mock_image = Image(
            key=None,
            url="https://example.com/upload/test.png",
            original_path="/tmp/test.png",
            uploaded_at=1234567890,
            image_type=ImageType.EYECATCH,
        )

        with patch("note_mcp.api.images._upload_image_internal") as mock_upload:
            mock_upload.return_value = mock_image

            result = await upload_eyecatch_chunked(
                session=session,
                upload_id="test-uuid-1",
                note_id="123456",
                mime_type="image/png",
                chunk=b64,
                chunk_index=0,
                total_chunks=1,
            )

        assert result is not None
        assert result.url == mock_image.url

    @pytest.mark.asyncio
    async def test_two_chunks(self) -> None:
        """Two-chunk upload should assemble and succeed."""
        from note_mcp.models import Image, ImageType

        session = _create_mock_session()
        raw = _create_test_png_bytes()
        b64 = base64.b64encode(raw).decode("ascii")

        # Split into two chunks
        mid = len(b64) // 2
        chunk1 = b64[:mid]
        chunk2 = b64[mid:]

        mock_image = Image(
            key=None,
            url="https://example.com/upload/test.png",
            original_path="/tmp/test.png",
            uploaded_at=1234567890,
            image_type=ImageType.EYECATCH,
        )

        with patch("note_mcp.api.images._upload_image_internal") as mock_upload:
            mock_upload.return_value = mock_image

            # First chunk - should return None
            result1 = await upload_eyecatch_chunked(
                session=session,
                upload_id="test-uuid-2",
                note_id="123456",
                mime_type="image/png",
                chunk=chunk1,
                chunk_index=0,
                total_chunks=2,
            )
            assert result1 is None

            # Second chunk - should assemble and upload
            result2 = await upload_eyecatch_chunked(
                session=session,
                upload_id="test-uuid-2",
                note_id="123456",
                mime_type="image/png",
                chunk=chunk2,
                chunk_index=1,
                total_chunks=2,
            )
            assert result2 is not None
            assert result2.url == mock_image.url

    @pytest.mark.asyncio
    async def test_three_chunks_out_of_order(self) -> None:
        """Out-of-order chunks should still assemble correctly."""
        from note_mcp.models import Image, ImageType

        session = _create_mock_session()
        raw = _create_test_png_bytes(width=20, height=20)
        b64 = base64.b64encode(raw).decode("ascii")

        chunk_size = len(b64) // 3
        chunks = [b64[i : i + chunk_size] for i in range(0, len(b64), chunk_size)]

        mock_image = Image(
            key=None,
            url="https://example.com/upload/test.png",
            original_path="/tmp/test.png",
            uploaded_at=1234567890,
            image_type=ImageType.EYECATCH,
        )

        with patch("note_mcp.api.images._upload_image_internal") as mock_upload:
            mock_upload.return_value = mock_image

            # Send in reverse order
            await upload_eyecatch_chunked(
                session=session,
                upload_id="test-uuid-3",
                note_id="123456",
                mime_type="image/png",
                chunk=chunks[2],
                chunk_index=2,
                total_chunks=3,
            )
            await upload_eyecatch_chunked(
                session=session,
                upload_id="test-uuid-3",
                note_id="123456",
                mime_type="image/png",
                chunk=chunks[1],
                chunk_index=1,
                total_chunks=3,
            )
            result = await upload_eyecatch_chunked(
                session=session,
                upload_id="test-uuid-3",
                note_id="123456",
                mime_type="image/png",
                chunk=chunks[0],
                chunk_index=0,
                total_chunks=3,
            )

        assert result is not None
        assert result.url == mock_image.url

    @pytest.mark.asyncio
    async def test_chunk_index_out_of_range(self) -> None:
        """Negative chunk_index should raise error."""
        session = _create_mock_session()

        with pytest.raises(NoteAPIError) as exc_info:
            await upload_eyecatch_chunked(
                session=session,
                upload_id="test-uuid-4",
                note_id="123456",
                mime_type="image/png",
                chunk="AAAA",
                chunk_index=-1,
                total_chunks=2,
            )
        assert exc_info.value.code == ErrorCode.INVALID_INPUT

    @pytest.mark.asyncio
    async def test_chunk_index_exceeds_total(self) -> None:
        """chunk_index >= total_chunks should raise error."""
        session = _create_mock_session()

        with pytest.raises(NoteAPIError) as exc_info:
            await upload_eyecatch_chunked(
                session=session,
                upload_id="test-uuid-5",
                note_id="123456",
                mime_type="image/png",
                chunk="AAAA",
                chunk_index=2,
                total_chunks=2,
            )
        assert exc_info.value.code == ErrorCode.INVALID_INPUT

    @pytest.mark.asyncio
    async def test_total_chunks_inconsistent(self) -> None:
        """Changing total_chunks between calls should raise error."""
        session = _create_mock_session()
        raw = _create_test_png_bytes()
        b64 = base64.b64encode(raw).decode("ascii")

        # First call with total_chunks=2
        await upload_eyecatch_chunked(
            session=session,
            upload_id="test-uuid-6",
            note_id="123456",
            mime_type="image/png",
            chunk=b64[:10],
            chunk_index=0,
            total_chunks=2,
        )

        # Second call with total_chunks=3 should fail
        with pytest.raises(NoteAPIError) as exc_info:
            await upload_eyecatch_chunked(
                session=session,
                upload_id="test-uuid-6",
                note_id="123456",
                mime_type="image/png",
                chunk=b64[10:],
                chunk_index=1,
                total_chunks=3,
            )
        assert exc_info.value.code == ErrorCode.INVALID_INPUT

    @pytest.mark.asyncio
    async def test_empty_upload_id(self) -> None:
        """Empty upload_id should raise error."""
        session = _create_mock_session()

        with pytest.raises(NoteAPIError) as exc_info:
            await upload_eyecatch_chunked(
                session=session,
                upload_id="  ",
                note_id="123456",
                mime_type="image/png",
                chunk="AAAA",
                chunk_index=0,
                total_chunks=1,
            )
        assert exc_info.value.code == ErrorCode.INVALID_INPUT

    @pytest.mark.asyncio
    async def test_empty_chunk(self) -> None:
        """Empty chunk should raise error."""
        session = _create_mock_session()

        with pytest.raises(NoteAPIError) as exc_info:
            await upload_eyecatch_chunked(
                session=session,
                upload_id="test-uuid-7",
                note_id="123456",
                mime_type="image/png",
                chunk="  ",
                chunk_index=0,
                total_chunks=2,
            )
        assert exc_info.value.code == ErrorCode.INVALID_BASE64

    @pytest.mark.asyncio
    async def test_state_cleaned_after_success(self) -> None:
        """Chunk buffer state should be cleaned after successful upload."""
        import note_mcp.api.images as img_mod
        from note_mcp.models import Image, ImageType

        session = _create_mock_session()
        raw = _create_test_png_bytes()
        b64 = base64.b64encode(raw).decode("ascii")

        mock_image = Image(
            key=None,
            url="https://example.com/upload/test.png",
            original_path="/tmp/test.png",
            uploaded_at=1234567890,
            image_type=ImageType.EYECATCH,
        )

        with patch("note_mcp.api.images._upload_image_internal") as mock_upload:
            mock_upload.return_value = mock_image

            result = await upload_eyecatch_chunked(
                session=session,
                upload_id="test-uuid-clean",
                note_id="123456",
                mime_type="image/png",
                chunk=b64,
                chunk_index=0,
                total_chunks=1,
            )

        assert result is not None
        assert "test-uuid-clean" not in img_mod._chunk_buffer

    @pytest.mark.asyncio
    async def test_state_cleaned_after_error(self) -> None:
        """Chunk buffer state should be cleaned even on upload failure."""
        import note_mcp.api.images as img_mod

        session = _create_mock_session()
        raw = _create_test_png_bytes()
        b64 = base64.b64encode(raw).decode("ascii")

        with patch("note_mcp.api.images._upload_image_internal") as mock_upload:
            mock_upload.side_effect = NoteAPIError(
                code=ErrorCode.API_ERROR,
                message="Upload failed",
            )

            with pytest.raises(NoteAPIError):
                await upload_eyecatch_chunked(
                    session=session,
                    upload_id="test-uuid-err",
                    note_id="123456",
                    mime_type="image/png",
                    chunk=b64,
                    chunk_index=0,
                    total_chunks=1,
                )

        assert "test-uuid-err" not in img_mod._chunk_buffer

    @pytest.mark.asyncio
    async def test_intermediate_returns_none(self) -> None:
        """Intermediate chunk should return None."""
        session = _create_mock_session()
        raw = _create_test_png_bytes()
        b64 = base64.b64encode(raw).decode("ascii")

        mid = len(b64) // 2
        result = await upload_eyecatch_chunked(
            session=session,
            upload_id="test-uuid-mid",
            note_id="123456",
            mime_type="image/png",
            chunk=b64[:mid],
            chunk_index=0,
            total_chunks=2,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_unsupported_mime_chunked(self) -> None:
        """Unsupported MIME type should raise on first chunk."""
        session = _create_mock_session()

        with pytest.raises(NoteAPIError) as exc_info:
            await upload_eyecatch_chunked(
                session=session,
                upload_id="test-uuid-mime",
                note_id="123456",
                mime_type="image/bmp",
                chunk="AAAA",
                chunk_index=0,
                total_chunks=1,
            )
        assert exc_info.value.code == ErrorCode.UNSUPPORTED_MIME_TYPE

    @pytest.mark.asyncio
    async def test_size_too_large_after_assembly(self) -> None:
        """Size check should happen after assembly."""
        from note_mcp.api import images

        session = _create_mock_session()

        # Create a known-size payload
        data = _create_test_png_bytes(width=2, height=2)
        b64 = base64.b64encode(data).decode("ascii")

        with patch.object(images, "MAX_FILE_SIZE", 5):
            with pytest.raises(NoteAPIError) as exc_info:
                await upload_eyecatch_chunked(
                    session=session,
                    upload_id="test-uuid-big",
                    note_id="123456",
                    mime_type="image/png",
                    chunk=b64,
                    chunk_index=0,
                    total_chunks=1,
                )
            assert exc_info.value.code == ErrorCode.IMAGE_TOO_LARGE


def tempfile_dir() -> str:
    """Get the tempfile directory."""
    import tempfile

    return tempfile.gettempdir()
