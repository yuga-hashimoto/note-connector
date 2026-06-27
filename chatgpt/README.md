# note-connector

ChatGPT **Connector** for [note.com](https://note.com) — MCP + Apps SDK UI.

## Install

```bash
npm install -g note-connector
```

## Requirements

- Node.js 20+
- [uv](https://docs.astral.sh/uv/) + Python 3.13+
- Git clone of this repository (MCP server):

```bash
git clone https://github.com/drillan/note-mcp.git
cd note-mcp && uv sync && uv run playwright install chromium
note-connector config set repoPath "$(pwd)"
```

## Run

```bash
note-connector
note-connector status
note-connector stop
```

See [full docs](https://github.com/drillan/note-mcp/blob/main/README.md).
