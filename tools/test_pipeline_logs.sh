#!/bin/bash
# Test pipeline step_logs output.
#
# Usage:
#   # With an existing document & conversation:
#   ./tools/test_pipeline_logs.sh <document_id> <conversation_id>
#
#   # Full flow: upload document, create conversation, upload data source, then run pipeline:
#   ./tools/test_pipeline_logs.sh --full <target_pdf> <data_source_file>
#
# Requires: curl, jq
# Server must be running at localhost:8000

set -euo pipefail

BASE_HOST="${API_BASE_HOST:-http://localhost:8000}"
V1="${BASE_HOST}/api/v1"
V2="${BASE_HOST}/api/v2"

# ============================================================================
# Colors for readability
# ============================================================================
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ============================================================================
# Helper: pretty-print step logs
# ============================================================================
print_step_logs() {
  local response="$1"

  local total_ms
  total_ms=$(echo "$response" | jq -r '.data.processing_time_ms // 0')
  local step_count
  step_count=$(echo "$response" | jq -r '.data.step_logs | length')

  echo ""
  echo -e "${BOLD}Pipeline Execution${NC}  (total: ${total_ms}ms, ${step_count} steps)"
  echo ""

  echo "$response" | jq -c '.data.step_logs[]' 2>/dev/null | while read -r step; do
    local name status duration summary error
    name=$(echo "$step" | jq -r '.step_name')
    status=$(echo "$step" | jq -r '.status')
    duration=$(echo "$step" | jq -r '.duration_ms')
    summary=$(echo "$step" | jq -r '.summary')
    error=$(echo "$step" | jq -r '.error // empty')

    # Status icon
    local icon
    if [ "$status" = "success" ]; then
      icon="${GREEN}✓${NC}"
    elif [ "$status" = "error" ]; then
      icon="${RED}✗${NC}"
    else
      icon="${GRAY}—${NC}"
    fi

    # Step label
    local label
    case "$name" in
      context_build) label="Context Build" ;;
      rule_analyze)  label="Rule Analysis" ;;
      fill_plan)     label="Fill Planning (LLM)" ;;
      render)        label="Render" ;;
      *)             label="$name" ;;
    esac

    # Print step header
    printf "  ${icon}  ${BOLD}%-24s${NC} %6sms\n" "$label" "$duration"
    echo -e "     ${GRAY}${summary}${NC}"

    # Print error if present
    if [ -n "$error" ]; then
      echo -e "     ${RED}Error: ${error}${NC}"
    fi

    # Print key details per step
    case "$name" in
      context_build)
        echo "$step" | jq -r '.details.data_sources[]? | "     \(.name) (\(.type)) — \(.field_count) fields"' 2>/dev/null
        echo "$step" | jq -r '.details.top_candidates[:5][]? | "     \(.field_id) ← \(.source_key) (\(.score))"' 2>/dev/null
        ;;
      fill_plan)
        local model
        model=$(echo "$step" | jq -r '.details.model_used // "n/a"')
        echo -e "     ${GRAY}model: ${model}${NC}"
        echo "$step" | jq -r '.details.actions[]? |
          if .action == "fill" then
            "     ✓ \(.field_id) = \"\(.value // "")\" (\((.confidence // 0) * 100 | floor)%)"
          elif .action == "skip" then
            "     ⊘ \(.field_id) — \(.reason // "skipped")"
          else
            "     ? \(.field_id) — \(.action)"
          end' 2>/dev/null
        ;;
      render)
        echo "$step" | jq -r '.details.field_results[]? |
          if .status == "success" then
            "     ✓ \(.field_id)"
          else
            "     ✗ \(.field_id) (\(.status))"
          end' 2>/dev/null
        ;;
    esac

    echo ""
  done
}

# ============================================================================
# Mode: Direct (document_id + conversation_id provided)
# ============================================================================
run_direct() {
  local doc_id="$1"
  local conv_id="$2"

  echo -e "${CYAN}=== Fetching fields for document ${doc_id} ===${NC}"
  local fields_resp
  fields_resp=$(curl -s "${V1}/documents/${doc_id}/acroform-fields")
  local field_count
  field_count=$(echo "$fields_resp" | jq '.data.fields | length')
  echo "Found ${field_count} fields"

  # Build fields array for request
  local fields_json
  fields_json=$(echo "$fields_resp" | jq '[.data.fields[] | {
    field_id: .field_name,
    label: .field_name,
    type: (.field_type // "text"),
    x: (.bbox.x // null),
    y: (.bbox.y // null),
    width: (.bbox.width // null),
    height: (.bbox.height // null),
    page: (.bbox.page // null)
  }]')

  echo -e "${CYAN}=== Running pipeline autofill ===${NC}"
  local request_body
  request_body=$(jq -n \
    --arg doc_id "$doc_id" \
    --arg conv_id "$conv_id" \
    --argjson fields "$fields_json" \
    '{document_id: $doc_id, conversation_id: $conv_id, fields: $fields}')

  local response
  response=$(curl -s -X POST "${V1}/autofill" \
    -H "Content-Type: application/json" \
    -d "$request_body")

  local success
  success=$(echo "$response" | jq -r '.data.success // false')

  if [ "$success" = "true" ]; then
    echo -e "${GREEN}Autofill succeeded${NC}"
  else
    local err
    err=$(echo "$response" | jq -r '.data.error // .error // "unknown error"')
    echo -e "${RED}Autofill failed: ${err}${NC}"
  fi

  # Print step logs
  print_step_logs "$response"

  # Also dump raw step_logs JSON for inspection
  echo -e "${CYAN}=== Raw step_logs JSON ===${NC}"
  echo "$response" | jq '.data.step_logs'
}

# ============================================================================
# Mode: Full flow (upload target + data source, then run)
# ============================================================================
run_full() {
  local target_pdf="$1"
  local data_source_file="$2"

  # 1. Upload target document (v1)
  echo -e "${CYAN}=== Uploading target document: ${target_pdf} ===${NC}"
  local upload_resp
  upload_resp=$(curl -s -X POST "${V1}/documents" \
    -F "file=@${target_pdf}" \
    -F "document_type=target")
  local doc_id
  doc_id=$(echo "$upload_resp" | jq -r '.data.document_id')
  echo "Document ID: ${doc_id}"

  if [ "$doc_id" = "null" ] || [ -z "$doc_id" ]; then
    echo -e "${RED}Failed to upload document:${NC}"
    echo "$upload_resp" | jq .
    exit 1
  fi

  # 2. Create conversation (v2 — returns Conversation directly, not wrapped in ApiResponse)
  local filename
  filename=$(basename "$target_pdf")
  echo -e "${CYAN}=== Creating conversation ===${NC}"
  local conv_resp
  conv_resp=$(curl -s -X POST "${V2}/conversations" \
    -H "Content-Type: application/json" \
    -d "{\"title\": \"Pipeline test: ${filename}\"}")
  local conv_id
  conv_id=$(echo "$conv_resp" | jq -r '.id')
  echo "Conversation ID: ${conv_id}"

  if [ "$conv_id" = "null" ] || [ -z "$conv_id" ]; then
    echo -e "${RED}Failed to create conversation:${NC}"
    echo "$conv_resp" | jq .
    exit 1
  fi

  # 3. Upload data source (v2)
  echo -e "${CYAN}=== Uploading data source: ${data_source_file} ===${NC}"
  local ds_resp
  ds_resp=$(curl -s -X POST "${V2}/conversations/${conv_id}/data-sources" \
    -F "file=@${data_source_file}")
  local ds_id
  ds_id=$(echo "$ds_resp" | jq -r '.data.id')
  echo "Data source ID: ${ds_id}"

  if [ "$ds_id" = "null" ] || [ -z "$ds_id" ]; then
    echo -e "${RED}Failed to upload data source:${NC}"
    echo "$ds_resp" | jq .
    exit 1
  fi

  # 4. Extract text from data source (v2)
  echo -e "${CYAN}=== Extracting text from data source ===${NC}"
  local extract_resp
  extract_resp=$(curl -s -X POST "${V2}/conversations/${conv_id}/data-sources/${ds_id}/extract")
  local extract_success
  extract_success=$(echo "$extract_resp" | jq -r '.success // false')
  if [ "$extract_success" = "true" ]; then
    local field_count
    field_count=$(echo "$extract_resp" | jq -r '.data.field_count // 0')
    echo -e "${GREEN}Extraction succeeded: ${field_count} fields extracted${NC}"
  else
    echo -e "${YELLOW}Extraction response:${NC}"
    echo "$extract_resp" | jq .
  fi

  # 5. Run pipeline
  run_direct "$doc_id" "$conv_id"

  echo ""
  echo -e "${YELLOW}Tip: Re-run with just IDs:${NC}"
  echo "  ./tools/test_pipeline_logs.sh ${doc_id} ${conv_id}"
}

# ============================================================================
# Main
# ============================================================================
if [ "${1:-}" = "--full" ]; then
  if [ $# -lt 3 ]; then
    echo "Usage: $0 --full <target_pdf> <data_source_file>"
    exit 1
  fi
  run_full "$2" "$3"
elif [ $# -ge 2 ]; then
  run_direct "$1" "$2"
else
  echo "Usage:"
  echo "  $0 <document_id> <conversation_id>"
  echo "  $0 --full <target_pdf> <data_source_file>"
  echo ""
  echo "Examples:"
  echo "  $0 abc123 conv456"
  echo "  $0 --full ./apps/tests/assets/2025bun_01_input.pdf ./apps/tests/assets/personal_info.txt"
  exit 1
fi
