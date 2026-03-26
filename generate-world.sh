#!/bin/bash
set -euo pipefail

# Load API key from .env
API_KEY=$(grep 'WLT_API_KEY' /Users/ryo/field-generate/.env | cut -d'=' -f2)
BASE_URL="https://api.worldlabs.ai/marble/v1"
IMAGE_PATH="/Users/ryo/field-generate/lapland.jpg"

echo "=== Step 1: Prepare upload ==="
PREPARE_RESPONSE=$(curl -s -X POST "${BASE_URL}/media-assets:prepare_upload" \
  -H 'Content-Type: application/json' \
  -H "WLT-Api-Key: ${API_KEY}" \
  -d '{
    "file_name": "lapland.jpg",
    "kind": "image",
    "extension": "jpg"
  }')

echo "$PREPARE_RESPONSE" | python3 -m json.tool

UPLOAD_URL=$(echo "$PREPARE_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['upload_info']['upload_url'])")
MEDIA_ASSET_ID=$(echo "$PREPARE_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['media_asset']['media_asset_id'])")

echo ""
echo "Media Asset ID: ${MEDIA_ASSET_ID}"

echo ""
echo "=== Step 2: Upload image ==="
curl -s -X PUT "${UPLOAD_URL}" \
  -H 'x-goog-content-length-range: 0,1048576000' \
  --data-binary "@${IMAGE_PATH}"

echo "Upload complete."

echo ""
echo "=== Step 3: Generate world ==="
GENERATE_RESPONSE=$(curl -s -X POST "${BASE_URL}/worlds:generate" \
  -H 'Content-Type: application/json' \
  -H "WLT-Api-Key: ${API_KEY}" \
  -d "{
    \"display_name\": \"Lapland Aurora\",
    \"world_prompt\": {
      \"type\": \"image\",
      \"image_prompt\": {
        \"source\": \"media_asset\",
        \"media_asset_id\": \"${MEDIA_ASSET_ID}\"
      },
      \"text_prompt\": \"A snowy Lapland landscape with bright green aurora borealis in the night sky, snow-covered pine trees, and a winter trail\"
    }
  }")

echo "$GENERATE_RESPONSE" | python3 -m json.tool

OPERATION_ID=$(echo "$GENERATE_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['operation_id'])")

echo ""
echo "Operation ID: ${OPERATION_ID}"
echo ""
echo "=== Step 4: Polling operation status ==="

while true; do
  POLL_RESPONSE=$(curl -s -X GET "${BASE_URL}/operations/${OPERATION_ID}" \
    -H "WLT-Api-Key: ${API_KEY}")

  DONE=$(echo "$POLL_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('done', False))")
  STATUS=$(echo "$POLL_RESPONSE" | python3 -c "import sys,json; m=json.load(sys.stdin).get('metadata'); print(m['progress']['status'] if m and 'progress' in m else 'UNKNOWN')" 2>/dev/null || echo "UNKNOWN")

  echo "$(date '+%H:%M:%S') - Status: ${STATUS}, Done: ${DONE}"

  if [ "$DONE" = "True" ]; then
    echo ""
    echo "=== World generation complete! ==="
    echo "$POLL_RESPONSE" | python3 -m json.tool

    WORLD_ID=$(echo "$POLL_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['metadata']['world_id'])")
    echo ""
    echo "View your world at: https://marble.worldlabs.ai/world/${WORLD_ID}"
    break
  fi

  # Check for error
  ERROR=$(echo "$POLL_RESPONSE" | python3 -c "import sys,json; e=json.load(sys.stdin).get('error'); print(e if e else '')" 2>/dev/null || echo "")
  if [ -n "$ERROR" ]; then
    echo "Error: ${ERROR}"
    exit 1
  fi

  sleep 15
done
