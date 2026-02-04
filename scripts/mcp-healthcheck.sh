#!/bin/bash
# MCP Server Health Check
#
# Usage:
#   ./scripts/mcp-healthcheck.sh
#   ./scripts/mcp-healthcheck.sh --verbose
#
# Exit codes:
#   0 = healthy
#   1 = unhealthy

set -e

VERBOSE=${1:-""}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Send initialize message and check for valid response
INIT_MSG='{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"healthcheck","version":"1.0"}}}'

if [ "$VERBOSE" = "--verbose" ] || [ "$VERBOSE" = "-v" ]; then
    echo "Checking MCP server health..."
    echo "Project dir: $PROJECT_DIR"
fi

# Run MCP server with initialize message, capture stdout only
RESPONSE=$(echo "$INIT_MSG" | docker compose \
    -f "$PROJECT_DIR/infra/docker-compose/docker-compose.dev.yml" \
    -f "$PROJECT_DIR/infra/docker-compose/docker-compose.mcp.yml" \
    run --rm -i mcp 2>/dev/null | grep -E '^\{.*"result".*\}$' | head -1)

if [ -z "$RESPONSE" ]; then
    echo "UNHEALTHY: No response from MCP server"
    exit 1
fi

# Check if response contains expected fields
if echo "$RESPONSE" | grep -q '"protocolVersion"' && echo "$RESPONSE" | grep -q '"serverInfo"'; then
    if [ "$VERBOSE" = "--verbose" ] || [ "$VERBOSE" = "-v" ]; then
        echo "Response: $RESPONSE"
    fi
    echo "HEALTHY: MCP server responded correctly"
    exit 0
else
    echo "UNHEALTHY: Invalid response from MCP server"
    echo "Response: $RESPONSE"
    exit 1
fi
