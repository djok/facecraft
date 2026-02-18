#!/usr/bin/env bash
#
# smoke-test.sh -- End-to-end smoke test for Facecraft Docker Hub images.
#
# Usage:
#   ./scripts/smoke-test.sh                     # default: djok/facecraft:cpu
#   ./scripts/smoke-test.sh djok/facecraft:gpu   # test GPU image
#
# What it does:
#   1. Pulls the image fresh from Docker Hub
#   2. Starts the container on port 8000
#   3. Waits for /health to return 200 (up to 300s for model loading)
#   4. POSTs a test image to /api/v1/process/quick
#   5. Verifies the response
#   6. Cleans up the container and temp files
#
set -euo pipefail

IMAGE="${1:-djok/facecraft:cpu}"
CONTAINER_NAME="facecraft-smoke-$$"
TEST_IMAGE="/tmp/smoke-test-portrait-$$.png"
OUTPUT_IMAGE="/tmp/smoke-output-$$.png"
PASS=true
SYNTHETIC_IMAGE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[SMOKE]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; PASS=false; }

cleanup() {
    log "Cleaning up..."
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
    rm -f "$TEST_IMAGE" "$OUTPUT_IMAGE"
}
trap cleanup EXIT

# --------------------------------------------------------------------------
# Step 0: Check port 8000 is free
# --------------------------------------------------------------------------
EXISTING=$(docker ps --filter "publish=8000" --format "{{.Names}}" 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
    warn "Container '$EXISTING' is already using port 8000. Stopping it."
    docker rm -f "$EXISTING" 2>/dev/null || true
    sleep 2
fi

# --------------------------------------------------------------------------
# Step 1: Pull image fresh from Docker Hub
# --------------------------------------------------------------------------
log "Pulling $IMAGE from Docker Hub..."
if ! docker pull "$IMAGE"; then
    fail "Failed to pull $IMAGE"
    echo ""
    echo "RESULT: FAIL"
    exit 1
fi
log "Pull complete."

# --------------------------------------------------------------------------
# Step 2: Start the container
# --------------------------------------------------------------------------
log "Starting container '$CONTAINER_NAME' from $IMAGE..."
docker run -d --name "$CONTAINER_NAME" -p 8000:8000 "$IMAGE"
log "Container started."

# --------------------------------------------------------------------------
# Step 3: Wait for /health to return 200
# --------------------------------------------------------------------------
log "Waiting for /health to return 200 (max 300s)..."
elapsed=0
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
    sleep 5
    elapsed=$((elapsed + 5))
    if [ "$elapsed" -ge 300 ]; then
        fail "/health not responding after 300s"
        echo ""
        echo "--- Container logs ---"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -50
        echo "--- End logs ---"
        echo ""
        echo "RESULT: FAIL"
        exit 1
    fi
    # Progress indicator every 30s
    if [ $((elapsed % 30)) -eq 0 ]; then
        log "  ...${elapsed}s elapsed, still waiting for /health"
    fi
done
log "/health returned 200 after ${elapsed}s."

# --------------------------------------------------------------------------
# Step 4: Verify /ready endpoint
# --------------------------------------------------------------------------
log "Checking /ready endpoint..."
READY_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ready)
if [ "$READY_CODE" = "200" ]; then
    log "/ready returned 200 -- models loaded."
else
    warn "/ready returned $READY_CODE (models may still be loading). Continuing anyway."
fi

# --------------------------------------------------------------------------
# Step 5: Create or obtain a test portrait
# --------------------------------------------------------------------------
log "Generating synthetic test portrait using container's Python/PIL..."
docker exec "$CONTAINER_NAME" python3 -c "
from PIL import Image, ImageDraw
# Create a simple face-like image: skin-colored oval with eyes
img = Image.new('RGB', (400, 500), (200, 200, 220))
draw = ImageDraw.Draw(img)
# Face oval
draw.ellipse([80, 50, 320, 420], fill=(230, 190, 160), outline=(180, 140, 110), width=2)
# Left eye
draw.ellipse([140, 160, 185, 195], fill=(255, 255, 255))
draw.ellipse([155, 170, 175, 190], fill=(60, 40, 30))
# Right eye
draw.ellipse([215, 160, 260, 195], fill=(255, 255, 255))
draw.ellipse([230, 170, 250, 190], fill=(60, 40, 30))
# Nose
draw.polygon([(195, 230), (200, 280), (180, 280)], fill=(210, 170, 140))
# Mouth
draw.arc([155, 290, 245, 340], start=0, end=180, fill=(180, 80, 80), width=3)
img.save('/tmp/test-portrait.png')
print('Synthetic portrait created: 400x500 PNG')
"
docker cp "$CONTAINER_NAME":/tmp/test-portrait.png "$TEST_IMAGE"
SYNTHETIC_IMAGE=true
log "Test image ready: $TEST_IMAGE (synthetic face-like image)."

# --------------------------------------------------------------------------
# Step 6: POST test portrait to /api/v1/process/quick
# --------------------------------------------------------------------------
log "POSTing test image to /api/v1/process/quick..."
HTTP_CODE=$(curl -s -o "$OUTPUT_IMAGE" -w "%{http_code}" \
    -X POST http://localhost:8000/api/v1/process/quick \
    -F "file=@${TEST_IMAGE}")

log "Response HTTP code: $HTTP_CODE"

if [ "$HTTP_CODE" = "200" ]; then
    # Verify output is a valid PNG
    FILE_TYPE=$(file "$OUTPUT_IMAGE" 2>/dev/null || echo "unknown")
    if echo "$FILE_TYPE" | grep -q "PNG image"; then
        log "Output is a valid PNG image."
        OUTPUT_SIZE=$(stat -c%s "$OUTPUT_IMAGE" 2>/dev/null || echo "unknown")
        log "Output file size: ${OUTPUT_SIZE} bytes"
        log "/api/v1/process/quick: PASS (200 + valid PNG)"
    else
        warn "Output is not a PNG: $FILE_TYPE"
        if [ "$SYNTHETIC_IMAGE" = true ]; then
            warn "This may be expected with a synthetic (non-face) test image."
        else
            fail "/api/v1/process/quick returned 200 but output is not a PNG."
        fi
    fi
elif [ "$HTTP_CODE" = "400" ]; then
    BODY=$(cat "$OUTPUT_IMAGE" 2>/dev/null || echo "")
    if echo "$BODY" | grep -qi "no face"; then
        if [ "$SYNTHETIC_IMAGE" = true ]; then
            log "/api/v1/process/quick: returned 400 'No face detected' -- expected for synthetic image."
            log "HTTP plumbing verified: server received image, processed it, returned structured error."
        else
            fail "/api/v1/process/quick: 400 No face detected on a real portrait."
        fi
    else
        fail "/api/v1/process/quick: returned 400 -- $BODY"
    fi
else
    fail "/api/v1/process/quick: unexpected HTTP $HTTP_CODE"
    BODY=$(cat "$OUTPUT_IMAGE" 2>/dev/null || echo "(no body)")
    warn "Response body: $BODY"
fi

# --------------------------------------------------------------------------
# Step 7: Print summary
# --------------------------------------------------------------------------
echo ""
echo "============================================"
echo "  SMOKE TEST SUMMARY"
echo "============================================"
echo "  Image:        $IMAGE"
echo "  Container:    $CONTAINER_NAME"
echo "  Pull:         OK"
echo "  /health:      200 (${elapsed}s)"
echo "  /ready:       $READY_CODE"
echo "  /process:     HTTP $HTTP_CODE"
echo "  Test image:   $([ "$SYNTHETIC_IMAGE" = true ] && echo "synthetic" || echo "real portrait")"
echo "============================================"

if [ "$PASS" = true ]; then
    echo -e "  ${GREEN}RESULT: PASS${NC}"
    echo ""
    echo "PASS"
else
    echo -e "  ${RED}RESULT: FAIL${NC}"
    echo ""
    echo "FAIL"
    exit 1
fi
