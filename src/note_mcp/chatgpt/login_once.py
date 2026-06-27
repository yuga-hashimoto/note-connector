"""One-shot note.com browser login for note-connector onboarding."""

from __future__ import annotations

import asyncio

from note_mcp.auth.browser import login_with_browser
from note_mcp.auth.session import SessionManager


async def _main() -> int:
    if SessionManager().has_session():
        print("note.com: already authenticated")
        return 0
    print("Opening browser for note.com login…")
    await login_with_browser(timeout=300)
    print("note.com: login saved")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
