#!/bin/bash
# MCP Server Full Test
#
# Tests MCP server initialization and tool functionality.
#
# Usage:
#   ./scripts/mcp-test.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "MCP Server Test Suite"
echo "=========================================="
echo ""

# Test messages
INIT_MSG='{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
LIST_TOOLS_MSG='{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
REGISTER_FORM_MSG='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"register_form","arguments":{"form_type":"Test Form","fields":[{"name":"field1","label":"Test Field","type":"text","required":true}]}}}'

# Combine messages
ALL_MSGS=$(cat <<EOF
$INIT_MSG
$LIST_TOOLS_MSG
$REGISTER_FORM_MSG
EOF
)

echo -e "${YELLOW}Running MCP server with test messages...${NC}"
echo ""

# Run and capture output
OUTPUT=$(echo "$ALL_MSGS" | docker compose \
    -f "$PROJECT_DIR/infra/docker-compose/docker-compose.dev.yml" \
    -f "$PROJECT_DIR/infra/docker-compose/docker-compose.mcp.yml" \
    run --rm -i mcp 2>&1)

# Show stderr logs
echo -e "${YELLOW}=== Server Logs ===${NC}"
echo "$OUTPUT" | grep -E '^\[' | head -20
echo ""

# Parse JSON responses
echo -e "${YELLOW}=== Test Results ===${NC}"

# Test 1: Initialize
if echo "$OUTPUT" | grep -q '"protocolVersion":"2025-06-18"'; then
    echo -e "${GREEN}✓ Initialize: PASSED${NC}"
else
    echo -e "${RED}✗ Initialize: FAILED${NC}"
fi

# Test 2: List Tools
TOOLS_COUNT=$(echo "$OUTPUT" | grep -o '"name":"[^"]*"' | wc -l)
if [ "$TOOLS_COUNT" -gt 5 ]; then
    echo -e "${GREEN}✓ List Tools: PASSED ($TOOLS_COUNT tools found)${NC}"
else
    echo -e "${RED}✗ List Tools: FAILED (only $TOOLS_COUNT tools found)${NC}"
fi

# Test 3: Register Form
if echo "$OUTPUT" | grep -q 'Form registered'; then
    FORM_ID=$(echo "$OUTPUT" | grep -o 'Form ID: `[^`]*`' | head -1 | sed 's/Form ID: `\([^`]*\)`/\1/')
    echo -e "${GREEN}✓ Register Form: PASSED (ID: ${FORM_ID:0:8}...)${NC}"
else
    echo -e "${RED}✗ Register Form: FAILED${NC}"
fi

# Test 4: Redis Connection
if echo "$OUTPUT" | grep -q 'Redis connected'; then
    echo -e "${GREEN}✓ Redis Connection: PASSED${NC}"
elif echo "$OUTPUT" | grep -q 'using in-memory storage'; then
    echo -e "${YELLOW}⚠ Redis Connection: Using in-memory fallback${NC}"
else
    echo -e "${RED}✗ Redis Connection: FAILED${NC}"
fi

echo ""
echo "=========================================="
echo "Test Complete"
echo "=========================================="
