# note-connector ChatGPT Connector — Design

## Scope

- npm package `note-connector` (app name: note-connector)
- No LocalAnt integration
- Python MCP + HTTP + Apps SDK widgets in this repository

## Architecture

- `chatgpt/` npm CLI: setup, start, tunnel, config
- `note_mcp.chatgpt`: HTTP `/mcp`, auth middleware, ChatGPT tools, widget resources
- Existing `note_mcp.server` tools reused over HTTP

## Delivered

- Tunnel: tailscale (default), ngrok, custom `tunnel.publicUrl`
- Tools: `note_attach_image`, `note_create_draft_with_images`, `note_ui_*`
- Widgets: home + article panel (`ui://note-connector/*`)
