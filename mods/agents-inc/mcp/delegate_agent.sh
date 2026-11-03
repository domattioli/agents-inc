#!/bin/sh
# Starts the DelegateAgent MCP server from the installed agents-inc release (spec 031 FR-013).
# The stable `current` link means a release upgrade needs no plugin change.
target="$HOME/.local/share/agents-inc/current/skills/codex-bridge/mcp/codex_agent_mcp.py"
if [ ! -f "$target" ]; then
    echo "agents-inc release not installed: $target is missing; run agents-inc install" >&2
    exit 1
fi
exec python3 "$target"
