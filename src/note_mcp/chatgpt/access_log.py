"""Record successful ChatGPT MCP access for note-connector CLI."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path


def _access_path() -> Path:
    base = Path(os.environ.get("NOTE_CONNECTOR_CONFIG_DIR", Path.home() / ".note-connector"))
    return base / "last-mcp-access.json"


def record_mcp_access(remote_host: str | None) -> None:
    """Append latest MCP access timestamp (idempotent overwrite)."""
    path = _access_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "at": datetime.now(UTC).isoformat(),
        "remote": remote_host,
    }
    import json

    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
