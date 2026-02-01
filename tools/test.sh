#!/bin/bash
BASE_URL="http://localhost:8000/api/v1"

# 1. アップロード
echo "=== Uploading document ==="
UPLOAD_RESP=$(curl -s -X POST "$BASE_URL/documents" \
  -F "file=@/Users/yasumasa_takemura/Downloads/2025bun_01_input.pdf" \
  -F "document_type=target")
DOC_ID=$(echo $UPLOAD_RESP | jq -r '.data.document_id')
echo "Document ID: $DOC_ID"

# 2. ジョブ作成
echo "=== Creating job ==="
JOB_RESP=$(curl -s -X POST "$BASE_URL/jobs" \
  -H "Content-Type: application/json" \
  -d "{\"mode\": \"scratch\", \"target_document_id\": \"$DOC_ID\"}")
JOB_ID=$(echo $JOB_RESP | jq -r '.data.job_id')
echo "Job ID: $JOB_ID"

# 3. 実行
echo "=== Running job ==="
RUN_RESP=$(curl -s -X POST "$BASE_URL/jobs/$JOB_ID/run" \
  -H "Content-Type: application/json" \
  -d '{"run_mode": "until_blocked"}')
STATUS=$(echo $RUN_RESP | jq -r '.data.status')
echo "Status: $STATUS"

# 4. レビュー確認
echo "=== Review ==="
curl -s "$BASE_URL/jobs/$JOB_ID/review" | jq '.data.issues'