# Phase 3: Publish and Document - Research

**Researched:** 2026-02-18
**Domain:** Docker Hub publishing, README documentation structure, smoke testing Docker images
**Confidence:** HIGH

## Summary

Phase 3 has three distinct concerns: (1) pushing the already-built `djok/facecraft:cpu` (4.08 GB) and `djok/facecraft:gpu` (13.8 GB) images to Docker Hub, (2) rewriting the README.md to be a Hub-first document with quickstart, benchmarks, env var reference, model inventory, image size transparency, and API overview, and (3) running a smoke test against the pulled Hub images to verify `/health` returns 200 and end-to-end image processing works.

The images are already built and tagged as `djok/facecraft:cpu` and `djok/facecraft:gpu` locally (confirmed via `docker images`). Pushing requires `docker login` authentication (via PAT or password) followed by `docker push djok/facecraft:cpu` and `docker push djok/facecraft:gpu`. The GPU image is 13.8 GB -- large but within Docker Hub's capabilities (no hard size limit). Docker pushes layers individually and skips layers already present on the registry, so subsequent pushes after the first will be fast. The prior decision to never push `:latest` means we push exactly two tags and nothing else.

Syncing the Docker Hub repository description from README.md requires the Docker Hub API. The endpoint is `PATCH https://hub.docker.com/v2/repositories/{namespace}/{repo}/` with a JSON body containing `full_description` (max 25,000 bytes) and optionally `description` (max 100 characters). Authentication uses a JWT token obtained from `POST https://hub.docker.com/v2/users/login/` or a Docker Hub Personal Access Token. The current README is 6,561 bytes -- well under the 25KB limit, and the rewritten version will also stay under this limit.

The smoke test needs a real portrait image with a detectable face -- a solid-color rectangle will not trigger face detection. The test script should: (1) pull the image from Hub, (2) start the container, (3) wait for `/health` to return 200, (4) POST a test portrait to `/api/v1/process/quick`, (5) verify the response is a valid PNG, (6) stop and remove the container.

**Primary recommendation:** Push both tags with `docker push` (not `docker compose push`), sync Hub description via the Hub API PATCH endpoint, rewrite README with Hub-pull quickstart as the opening content, and run a shell-based smoke test script that validates health and end-to-end processing against the pulled images.

## Standard Stack

### Core

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `docker push` | Docker CLI (any modern) | Push images to Docker Hub | Standard CLI for registry operations |
| Docker Hub API v2 | Current | Sync repository description | Only programmatic way to update Hub README |
| `curl` | Any | HTTP requests in smoke tests | Available everywhere, installed in both images |

### Supporting

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `docker login` | Authenticate to Docker Hub before push | Required once before any push operation |
| `docker pull` | Pull images from Hub for smoke test | Verifies the pushed images are actually pullable |
| `docker run` | Start container for smoke test | Runs the pulled image for verification |
| `jq` | Parse JSON responses in smoke test | Validate API response structure |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `docker push` per tag | `docker compose push` | Compose push works but requires `--profile` activation; plain `docker push` is simpler and more explicit for two known tags |
| Hub API PATCH for description | `peter-evans/dockerhub-description` GitHub Action | The Action is for CI/CD; for a one-time manual sync, a curl command is simpler |
| Shell script smoke test | Docker Compose test profile | A standalone script is more portable and tests the pull-from-Hub scenario specifically |

## Architecture Patterns

### Pattern 1: Push Specific Tags Only (No `:latest`)

**What:** Push exactly `djok/facecraft:cpu` and `djok/facecraft:gpu` -- never `:latest`.
**When to use:** Always. This is a locked prior decision.
**Why:** Avoids ambiguity about what `:latest` means when CPU and GPU are different images. Users must explicitly choose their variant.

```bash
# Images are already tagged from the build phase
docker push djok/facecraft:cpu
docker push djok/facecraft:gpu
```

### Pattern 2: Docker Hub Description Sync via API

**What:** Update the Docker Hub repository description and full_description (README) via the Hub API.
**When to use:** After README.md is finalized, to keep Hub overview in sync.
**Constraints:** `description` max 100 chars, `full_description` max 25,000 bytes.

```bash
# Step 1: Get JWT token
TOKEN=$(curl -s -H "Content-Type: application/json" \
  -X POST -d '{"username":"'"$DOCKER_USER"'","password":"'"$DOCKER_PASS"'"}' \
  https://hub.docker.com/v2/users/login/ | jq -r .token)

# Step 2: Update repository description
curl -s -X PATCH -L \
  "https://hub.docker.com/v2/repositories/djok/facecraft/" \
  -H "Content-Type: application/json" \
  -H "Authorization: JWT ${TOKEN}" \
  -d @- <<EOF
{
  "description": "AI portrait processing API - background removal, face detection, alignment, enhancement",
  "full_description": "$(cat README.md | jq -Rs .)"
}
EOF
```

**Note:** The JSON body requires the README content to be properly escaped. Using `jq -Rs .` handles newlines and special characters.

### Pattern 3: Smoke Test Against Pulled Hub Image

**What:** A self-contained test script that pulls from Hub, starts the container, checks health, processes an image, and cleans up.
**When to use:** After push, to verify the published images work for end users.
**Critical requirement:** The test needs a real portrait image with a detectable human face -- synthetic/blank images will fail face detection.

```bash
#!/usr/bin/env bash
set -euo pipefail

IMAGE="djok/facecraft:cpu"
CONTAINER_NAME="facecraft-smoke-test"
PORT=8000
MAX_WAIT=300  # 5 minutes (model loading takes time, start_period is 180s)

# 1. Pull from Hub
docker pull "$IMAGE"

# 2. Start container
docker run -d --name "$CONTAINER_NAME" -p "${PORT}:8000" "$IMAGE"

# 3. Wait for /health to return 200
echo "Waiting for container to be healthy..."
elapsed=0
until curl -sf "http://localhost:${PORT}/health" > /dev/null 2>&1; do
  sleep 5
  elapsed=$((elapsed + 5))
  if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    echo "FAIL: Container did not become healthy within ${MAX_WAIT}s"
    docker logs "$CONTAINER_NAME"
    docker rm -f "$CONTAINER_NAME"
    exit 1
  fi
done
echo "OK: /health returned 200 after ${elapsed}s"

# 4. Process a test image
RESPONSE=$(curl -s -o /tmp/smoke-test-output.png -w "%{http_code}" \
  -X POST "http://localhost:${PORT}/api/v1/process/quick" \
  -F "file=@test-portrait.jpg")

if [ "$RESPONSE" = "200" ]; then
  # Verify output is a valid PNG (magic bytes: 89 50 4E 47)
  if file /tmp/smoke-test-output.png | grep -q "PNG image"; then
    echo "OK: Image processed successfully, valid PNG returned"
  else
    echo "FAIL: Response was 200 but output is not a valid PNG"
    docker rm -f "$CONTAINER_NAME"
    exit 1
  fi
else
  echo "FAIL: Image processing returned HTTP $RESPONSE"
  docker rm -f "$CONTAINER_NAME"
  exit 1
fi

# 5. Cleanup
docker rm -f "$CONTAINER_NAME"
rm -f /tmp/smoke-test-output.png
echo "PASS: All smoke tests passed"
```

### Pattern 4: Hub-First README Structure

**What:** README opens with Docker Hub pull quickstart and benchmarks -- not build instructions.
**When to use:** When images are published on Docker Hub and pulling is the primary consumption path.
**Rationale:** The first thing a developer sees should be "how to use this in 30 seconds."

Recommended section order for the rewritten README:

```
1. Title + one-line description
2. Docker Hub quickstart (docker run one-liner)
3. Performance benchmarks table (CPU vs GPU)
4. API endpoint overview with curl examples
5. Environment variable reference table
6. Bundled models inventory table
7. Image size transparency section
8. Volume mount examples for data persistence
9. Docker Compose usage
10. Development / local setup
11. License and acknowledgments
```

### Anti-Patterns to Avoid

- **Pushing `:latest` tag:** Prior decision forbids this. Users must specify `:cpu` or `:gpu`.
- **Build-first README:** The README currently opens with `docker build` instructions. This must change to `docker pull`/`docker run` from Hub.
- **Missing Hub description sync:** Pushing images without updating the Hub overview leaves the repository description empty/stale.
- **Smoke testing with synthetic images:** A blank or gradient image will not have a detectable face, causing the smoke test to "pass" the HTTP call but not validate actual processing. Must use a real portrait.
- **Hardcoding benchmark numbers from different hardware:** The existing benchmarks are from specific hardware (Ryzen 9 7900 + RTX 4090). These should be preserved with the hardware specification clearly stated.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON escaping for Hub API | Manual string replacement | `jq -Rs .` to escape README content | Handles all special chars, newlines, quotes |
| Health wait loop | Ad-hoc sleep + curl | Structured retry loop with timeout | Must handle the 180s start_period for model loading |
| PNG validation | Custom byte reading | `file` command (checks magic bytes) | Standard Unix tool, reliable magic byte detection |
| README content | Writing from scratch | Adapt existing README sections | Current README already has benchmarks, env vars, API docs -- restructure, don't recreate |

**Key insight:** The existing README already contains most required content (benchmarks, env vars, API endpoints, model list). The task is restructuring and completing it, not writing from nothing.

## Common Pitfalls

### Pitfall 1: Docker Hub Authentication Failure

**What goes wrong:** `docker push` fails with "denied: requested access to the resource is denied".
**Why it happens:** Not logged in, wrong credentials, or token lacks write permission.
**How to avoid:** Run `docker login` before push. Verify with `docker info | grep Username`. If using a PAT, ensure it has "Read & Write" scope (not just "Read").
**Warning signs:** Any "denied" or "unauthorized" error from `docker push`.

### Pitfall 2: Large Image Push Timeout or Failure

**What goes wrong:** Push of the 13.8 GB GPU image stalls, times out, or fails partway through.
**Why it happens:** Large layer uploads can fail on unstable connections. Docker pushes 5 layers concurrently by default.
**How to avoid:** Push the CPU image first (4 GB, faster feedback). For the GPU image, be prepared for a long upload. If it fails, re-running `docker push` will skip already-uploaded layers. Reduce concurrent uploads with `--max-concurrent-uploads` daemon option if bandwidth is limited.
**Warning signs:** Push progress stalls for extended periods or connection resets.

### Pitfall 3: Hub Description Too Long

**What goes wrong:** PATCH to Hub API returns 400 error.
**Why it happens:** `full_description` exceeds 25,000 bytes or `description` exceeds 100 characters.
**How to avoid:** Check README size before syncing: `wc -c README.md`. Current README is 6,561 bytes. The rewritten version should stay well under 25KB. Keep the short `description` field under 100 chars.
**Warning signs:** HTTP 400 from the Hub API PATCH endpoint.

### Pitfall 4: Smoke Test Timeout During Model Loading

**What goes wrong:** The smoke test curl fails because the container is still loading models when the test runs.
**Why it happens:** The Dockerfiles have `start_period: 180s` because model loading takes significant time (up to 3 minutes). The `/health` endpoint returns 200 as soon as FastAPI starts, but models may not be fully loaded yet. The `/ready` endpoint waits for models.
**How to avoid:** The smoke test should wait for `/health` to return 200 (proving the process is up), then use `/api/v1/process/quick` which will naturally wait for models to be loaded (it depends on the processor which loads models at startup via the lifespan handler). If the first processing request takes longer, that is expected -- the model loading happens during the lifespan startup, before any request can be served. So if `/health` returns 200, the models should already be loaded.
**Clarification:** Looking at the code, `/health` returns 200 immediately when FastAPI is up. But the `lifespan` function calls `init_processor()` which loads all models BEFORE yielding. So by the time any request handler runs (including `/health`), models are already loaded. The start_period in the Dockerfile HEALTHCHECK is just to give curl time to succeed during the initial startup.
**Warning signs:** Timeout waiting for health; or health succeeds but processing fails.

### Pitfall 5: No Test Portrait Image Available

**What goes wrong:** Smoke test has no image to POST, or uses a non-portrait image that fails face detection.
**Why it happens:** The project has no test images (confirmed: no `.jpg` or `.png` files in the repo). The `.dockerignore` excludes test files.
**How to avoid:** The smoke test plan must include creating or downloading a test portrait image. Options: (1) download a Creative Commons portrait from the internet during test setup, (2) include a small test portrait in the repo (e.g., `tests/fixtures/test-portrait.jpg`), or (3) generate a synthetic face image programmatically. Option 2 is most reliable -- a small (~50KB) portrait JPEG checked into the repo guarantees the test is self-contained.
**Warning signs:** HTTP 400 "No face could be detected" from the processing endpoint.

### Pitfall 6: README Hub Sync JSON Escaping

**What goes wrong:** The PATCH request to Hub API fails or corrupts the README content.
**Why it happens:** The README contains characters that need JSON escaping (quotes, backslashes, newlines). Manual escaping is error-prone.
**How to avoid:** Use `jq -Rs . < README.md` to produce a properly escaped JSON string, then embed it in the PATCH payload. Alternatively, use a tool like `python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))" < README.md`.
**Warning signs:** Malformed JSON error from the API, or garbled README on Docker Hub.

## Code Examples

### Docker Push Workflow

```bash
# Prerequisite: docker login (interactive, one-time)
docker login
# Or non-interactive with PAT:
# echo "$DOCKER_HUB_PAT" | docker login --username djok --password-stdin

# Push CPU image (4.08 GB) -- push this first for faster feedback
docker push djok/facecraft:cpu

# Push GPU image (13.8 GB) -- this will take longer
docker push djok/facecraft:gpu

# Verify push succeeded by checking the Hub
# (Optional: pull to a different location to verify)
```

### Docker Hub Description Sync

```bash
# Get authentication token
TOKEN=$(curl -s -H "Content-Type: application/json" \
  -X POST -d '{"username":"'"$DOCKER_USER"'","password":"'"$DOCKER_PASS"'"}' \
  https://hub.docker.com/v2/users/login/ | jq -r .token)

# Prepare the README content as escaped JSON
README_JSON=$(jq -Rs . < README.md)

# Update Hub repository description
curl -X PATCH -L \
  "https://hub.docker.com/v2/repositories/djok/facecraft/" \
  -H "Content-Type: application/json" \
  -H "Authorization: JWT ${TOKEN}" \
  -d "{\"description\":\"AI portrait processing API with background removal, face detection, and enhancement\",\"full_description\":${README_JSON}}"
```

### README Structure Template

```markdown
# Facecraft

AI-powered portrait processing API with background removal, face detection,
alignment, and enhancement.

## Quick Start

```bash
docker run -p 8000:8000 djok/facecraft:cpu
```

Then open http://localhost:8000/docs or:

```bash
# Health check
curl http://localhost:8000/health

# Process a portrait (returns PNG directly)
curl -X POST http://localhost:8000/api/v1/process/quick \
  -F "file=@photo.jpg" -o processed.png
```

## Performance

| Version | Image | Avg. Time/Image | Speedup |
|---------|-------|-----------------|---------|
| CPU | `djok/facecraft:cpu` | ~1.45s | 1x baseline |
| GPU | `djok/facecraft:gpu` | ~0.43s | 3.4x faster |

*Tested on: AMD Ryzen 9 7900, 32GB DDR5, NVIDIA RTX 4090. 5 portrait images, 648x648 output.*

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FACECRAFT_HOST` | `0.0.0.0` | Bind address |
| `FACECRAFT_PORT` | `8000` | API port |
| ... | ... | ... |

## Bundled Models

| Model | File | Size | Purpose |
|-------|------|------|---------|
| dlib shape predictor | shape_predictor_68_face_landmarks.dat | ~95 MB | Face landmark detection (68 points) |
| CodeFormer | codeformer.pth | ~350 MB | AI face quality enhancement |
| u2net_human_seg | u2net_human_seg.onnx | ~170 MB | Background removal segmentation |

## Image Sizes

| Tag | Compressed (Hub) | Uncompressed | Why It's Large |
|-----|-------------------|--------------|----------------|
| `djok/facecraft:cpu` | ~TBD | 4.08 GB | PyTorch 2.0.1 (~1.8 GB) + models (~615 MB) + runtime |
| `djok/facecraft:gpu` | ~TBD | 13.8 GB | CUDA 12.1 runtime (~1.1 GB) + PyTorch+CUDA (~5.9 GB) + models (~615 MB) |

*All models are bundled -- no downloads on first run.*

...
```

### Complete Environment Variable Reference (from config.py)

The following is the complete set of `FACECRAFT_*` environment variables extracted from `src/facecraft/core/config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `FACECRAFT_HOST` | `0.0.0.0` | Server bind address |
| `FACECRAFT_PORT` | `8000` | Server port |
| `FACECRAFT_WORKERS` | `1` | Number of Uvicorn workers |
| `FACECRAFT_DEBUG` | `false` | Enable debug mode (hot reload) |
| `FACECRAFT_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `FACECRAFT_DEVICE` | `auto` | Compute device: `auto`, `cpu`, `cuda`, `cuda:0` |
| `FACECRAFT_MODELS_DIR` | `/app/models` | Path to model files directory |
| `FACECRAFT_PREDICTOR_PATH` | (auto) | Override path to dlib shape predictor |
| `FACECRAFT_CODEFORMER_PATH` | (auto) | Override path to CodeFormer model |
| `FACECRAFT_DEFAULT_WIDTH` | `648` | Default output image width |
| `FACECRAFT_DEFAULT_HEIGHT` | `648` | Default output image height |
| `FACECRAFT_DEFAULT_BACKGROUND_R` | `240` | Default background red channel |
| `FACECRAFT_DEFAULT_BACKGROUND_G` | `240` | Default background green channel |
| `FACECRAFT_DEFAULT_BACKGROUND_B` | `240` | Default background blue channel |
| `FACECRAFT_DEFAULT_FACE_MARGIN` | `0.3` | Default margin around detected face (0.0-1.0) |
| `FACECRAFT_DEFAULT_OVAL_MASK` | `true` | Apply oval mask by default |
| `FACECRAFT_DEFAULT_ENHANCE_FIDELITY` | `0.7` | CodeFormer fidelity weight (0.0-1.0) |
| `FACECRAFT_UPLOAD_DIR` | `/app/uploads` | Directory for uploaded files |
| `FACECRAFT_OUTPUT_DIR` | `/app/processed` | Directory for processed output |
| `FACECRAFT_MAX_UPLOAD_SIZE_MB` | `20` | Maximum upload file size in MB |
| `FACECRAFT_CLEANUP_AGE_HOURS` | `24` | Auto-delete files older than N hours |
| `FACECRAFT_MAX_CONCURRENT_JOBS` | `4` | Maximum parallel processing jobs |
| `FACECRAFT_BATCH_MAX_FILES` | `50` | Maximum files in batch request |
| `FACECRAFT_CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |
| `FACECRAFT_API_KEY` | (none) | Optional API key for authentication |

### Image Size Breakdown (from docker history)

**CPU Image (4.08 GB uncompressed):**

| Layer | Size | Contents |
|-------|------|----------|
| Python packages (wheels) | 1.84 GB | PyTorch 2.0.1 CPU, FastAPI, dlib, rembg, etc. |
| Wheel build artifacts | 528 MB | Copied from builder stage |
| Models + permissions | 652 MB | chown after model copy |
| CodeFormer model | 377 MB | codeformer.pth |
| u2net model | 176 MB | u2net_human_seg.onnx |
| Shape predictor | 99.7 MB | shape_predictor_68_face_landmarks.dat |
| Runtime apt packages | 286 MB | libopenblas, libgl1, curl, etc. |
| Base image | ~120 MB | python:3.11-slim |

**GPU Image (13.8 GB uncompressed):**

| Layer | Size | Contents |
|-------|------|----------|
| Python packages (wheels) | 5.89 GB | PyTorch 2.0.1+cu118, CUDA libs, etc. |
| Wheel build artifacts | 2.95 GB | Copied from builder stage |
| NVIDIA CUDA base | 1.14 GB | cuda:12.1.0-cudnn8-runtime |
| Models + permissions | 652 MB | Same as CPU |
| CodeFormer model | 377 MB | codeformer.pth |
| Runtime apt packages | 340 MB | Python 3.11, libs, curl |
| u2net model | 176 MB | u2net_human_seg.onnx |
| Shape predictor | 99.7 MB | shape_predictor_68_face_landmarks.dat |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Build-from-source README | Hub-pull-first README | When images published to Hub | Users can run in 10 seconds instead of building for 30+ minutes |
| Password-based `docker login` | PAT-based authentication | Docker Hub security updates (2023+) | More secure, token can be scoped and revoked |
| Manual Hub description editing | API-based sync from README.md | Docker Hub API v2 | Keeps Hub overview in sync with repo README automatically |

**Deprecated/outdated:**
- Using `docker login` with password in CLI args: Use `--password-stdin` to avoid password in shell history.
- Docker Hub JWT login endpoint may be deprecated in favor of PATs for API access. PATs can also be used as Bearer tokens with the Hub API.

## Open Questions

1. **Docker Hub authentication method for the user**
   - What we know: `docker login` is required before push. Both password and PAT methods work.
   - What's unclear: Whether the user (`djok`) already has Docker Hub credentials configured, or if this is a first-time setup.
   - Recommendation: The plan should include a `docker login` step but note it is interactive and requires the user's credentials. Do not hardcode or commit credentials.

2. **Compressed image size on Docker Hub**
   - What we know: Uncompressed sizes are 4.08 GB (CPU) and 13.8 GB (GPU). Docker Hub stores compressed layers.
   - What's unclear: The exact compressed sizes are unknown until after the first push.
   - Recommendation: Leave the "Compressed (Hub)" column in the image size table as "TBD" during README writing, then update after push with actual Hub-reported sizes. Alternatively, check with `docker image inspect --format '{{.Size}}'` and `docker manifest inspect` after push.

3. **Test portrait image source**
   - What we know: The project has no test images. Face detection requires a real portrait.
   - What's unclear: Whether to include a test image in the repo or download one during testing.
   - Recommendation: Download a small public-domain portrait during the smoke test setup step (e.g., from Unsplash or a direct URL). This avoids adding binary files to the repo. Alternatively, use `python3` with Pillow inside the container to generate a synthetic image -- but this will likely fail face detection. Best option: download a known CC0 portrait and save it to a temp directory for the test.

4. **Upload time for GPU image**
   - What we know: 13.8 GB uncompressed. Compressed will be smaller. Docker pushes layers in parallel (default 5 concurrent).
   - What's unclear: Actual upload time depends on connection bandwidth.
   - Recommendation: Plan should push CPU first, verify it works, then push GPU. This provides faster feedback and a fallback if the GPU push is interrupted.

## Sources

### Primary (HIGH confidence)
- [Docker Push CLI Reference](https://docs.docker.com/reference/cli/docker/image/push/) - Push syntax, flags, layer deduplication behavior
- [Docker Compose Push Reference](https://docs.docker.com/reference/cli/docker/compose/push/) - Compose push syntax, service selection, flags
- [Docker Hub Usage and Limits](https://docs.docker.com/docker-hub/usage/) - Pull rate limits, account tiers
- [Docker Hub Personal Access Tokens](https://docs.docker.com/security/access-tokens/) - PAT creation, scopes (Read/Write/Delete), CLI login usage
- [Docker Hub Repository Information](https://docs.docker.com/docker-hub/repos/manage/information/) - Description limits (100 chars short, 25KB full)

### Secondary (MEDIUM confidence)
- [Docker Hub API v2 PATCH endpoint](https://github.com/docker/hub-feedback/issues/2321) - Community-confirmed PATCH endpoint for repository description updates
- [peter-evans/dockerhub-description](https://github.com/peter-evans/dockerhub-description) - Confirms API endpoint and authentication pattern for Hub description sync
- [Docker Hub API Reference](https://docs.docker.com/reference/api/hub/latest/) - OpenAPI spec available (interactive docs)

### Project Sources (HIGH confidence)
- `docker/Dockerfile.cpu` - CPU image structure, 3-stage build, model locations, user configuration
- `docker/Dockerfile.gpu` - GPU image structure, CUDA 12.1 base, NVIDIA env vars
- `docker-compose.yml` - Service definitions, `image:` keys set to `djok/facecraft:cpu` and `djok/facecraft:gpu`
- `src/facecraft/core/config.py` - Complete `FACECRAFT_*` environment variable definitions with defaults
- `src/facecraft/api/routes/health.py` - `/health` (liveness), `/ready` (readiness), `/status` (detailed) endpoints
- `src/facecraft/api/routes/process.py` - `/api/v1/process`, `/api/v1/process/quick`, `/api/v1/process/batch` endpoints
- `.env.example` - Environment variable reference file
- `src/facecraft/__init__.py` - Version is `1.0.0`
- `docker images` output - CPU: 4.08 GB, GPU: 13.8 GB (uncompressed, local)
- `docker history` output - Layer-by-layer size breakdown for both images

## Metadata

**Confidence breakdown:**
- Docker push workflow: HIGH - Standard Docker CLI operations, well-documented
- Hub description sync: MEDIUM - API endpoint confirmed by multiple community sources, but not explicitly in official interactive docs
- README structure: HIGH - Requirements are explicit (DOCS-01 through DOCS-07), all content already exists in current README or config.py
- Smoke test approach: HIGH - Standard container testing pattern; the only uncertainty is the test portrait image source
- Image size breakdown: HIGH - Extracted directly from `docker history` of actually-built images
- Environment variable reference: HIGH - Extracted directly from `src/facecraft/core/config.py` source code

**Research date:** 2026-02-18
**Valid until:** 2026-03-18 (Docker Hub API is stable; Docker push workflow is stable; 30-day estimate)
