# Phase 2: Build, Verify, and Orchestrate - Research

**Researched:** 2026-02-18
**Domain:** Docker image building/verification, Docker Compose orchestration with profiles and GPU support
**Confidence:** HIGH

## Summary

Phase 2 bridges the gap between hardened Dockerfiles (Phase 1 complete) and a production-ready deployment configuration. It has two distinct concerns: (1) building both Docker images and verifying they are correct, self-contained, and non-root, and (2) writing a docker-compose.yml that uses Compose profiles to allow CPU-only or GPU deployment from a single file.

The Docker Compose specification is the primary technical domain. Modern Compose files no longer use a `version:` key (obsolete since v2.25.0, produces warnings). Profiles allow mutually exclusive services on the same port -- critical here since both CPU and GPU services expose 8000. GPU passthrough uses `deploy.resources.reservations.devices` with `driver: nvidia` and `capabilities: [gpu]`. Volume mounts for `/app/uploads` and `/app/processed` need careful permission handling because the container runs as `appuser` (UID 1000) and named volumes are created as root by default.

The verification checklist is straightforward but requires the images to actually be built, which is a long-running operation (model downloads are ~600MB, dlib compilation takes minutes). The `--network none` test proves air-gap self-containment. The `whoami` test proves non-root execution. The `docker compose config --quiet` command validates compose syntax without starting services.

**Primary recommendation:** Write a single `docker-compose.yml` at repo root with no `version:` key, two profiled services (`facecraft-cpu` and `facecraft-gpu`) on the same port 8000, named volumes for data persistence, and inline YAML comments documenting every environment variable. Use `docker compose config --quiet` for syntax validation before testing profiles.

## Standard Stack

### Core

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Docker Compose | v2 (Compose Specification) | Service orchestration | Standard for multi-container Docker apps; profiles are native |
| Docker Engine | 24.x+ | Image building and running | Required for compose v2 and GPU support |
| NVIDIA Container Toolkit | Latest | GPU passthrough in containers | Required for `deploy.resources.reservations.devices` |

### Supporting

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `docker compose config` | Validate compose YAML syntax | Before starting any services -- catches parse errors |
| `docker run --network none` | Air-gap self-containment test | Verify image has all models bundled, needs no internet |
| `docker inspect` | Verify image metadata (labels, user) | Confirm OCI labels and USER directive are correct |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Compose profiles | Separate compose files (docker-compose.cpu.yml / docker-compose.gpu.yml) | Profiles keep everything in one file; the requirement (COMP-01) mandates single file with profiles |
| Named volumes | Bind mounts (./data:/app/uploads) | Named volumes are portable; bind mounts are host-dependent. Named volumes are preferred for production |
| `deploy.resources.reservations.devices` | `runtime: nvidia` + NVIDIA_VISIBLE_DEVICES env | The deploy syntax is the modern standard; runtime key is the legacy approach |

## Architecture Patterns

### Recommended Compose File Structure

```yaml
# docker-compose.yml (repo root)
# No version: key -- obsolete since Compose v2.25.0

services:
  facecraft-cpu:
    profiles: [cpu]
    # ... CPU service config

  facecraft-gpu:
    profiles: [gpu]
    # ... GPU service config with deploy.resources.reservations.devices

volumes:
  uploads:
  processed:
```

### Pattern 1: Mutually Exclusive Profile Services on Same Port

**What:** Two services sharing the same host port (8000:8000), each in a different profile, so only one runs at a time.
**When to use:** When you have CPU and GPU variants of the same application.
**Why it works:** Profiles are mutually exclusive by activation -- `docker compose --profile cpu up` only starts services with `profiles: [cpu]`. Services without a `profiles` attribute always start, so DO NOT leave either service unassigned.

```yaml
# Source: https://docs.docker.com/compose/how-tos/profiles/
services:
  facecraft-cpu:
    profiles: [cpu]
    image: djok/facecraft:cpu
    ports:
      - "8000:8000"

  facecraft-gpu:
    profiles: [gpu]
    image: djok/facecraft:gpu
    ports:
      - "8000:8000"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

### Pattern 2: GPU Device Reservation

**What:** The `deploy.resources.reservations.devices` specification for NVIDIA GPU passthrough.
**When to use:** Any Docker Compose service needing GPU access.
**Critical constraint:** `count` and `device_ids` are mutually exclusive -- Compose returns an error if both are specified.
**Required field:** `capabilities: [gpu]` MUST be set -- omitting it causes a deployment error.

```yaml
# Source: https://docs.docker.com/compose/how-tos/gpu-support/
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all       # or integer, or use device_ids instead
          capabilities: [gpu]
```

### Pattern 3: Named Volumes for Data Persistence

**What:** Declare named volumes at top level, reference in services for `/app/uploads` and `/app/processed`.
**When to use:** When container data must survive restarts and image updates.
**Permission note:** Named volumes created by Docker are root-owned by default, but Compose populates them from the container image on first use -- since the Dockerfile creates these directories owned by `appuser:appuser`, the permissions propagate correctly on first volume creation.

```yaml
# Source: https://docs.docker.com/reference/compose-file/volumes/
services:
  facecraft-cpu:
    volumes:
      - uploads:/app/uploads
      - processed:/app/processed

volumes:
  uploads:
  processed:
```

### Pattern 4: Build from Dockerfile in Subdirectory

**What:** Use the `build` key with `context` (repo root) and `dockerfile` (path to specific Dockerfile).
**When to use:** When Dockerfiles live in `docker/` but the build context must be the repo root (for COPY requirements.txt etc.).

```yaml
# Source: https://docs.docker.com/reference/compose-file/build/
services:
  facecraft-cpu:
    build:
      context: .
      dockerfile: docker/Dockerfile.cpu
    image: djok/facecraft:cpu
```

### Anti-Patterns to Avoid

- **Using `version:` key:** Obsolete since Compose v2.25.0. Produces a warning; newer versions may error. Omit entirely.
- **Services without profiles sharing the same port:** Both would try to bind 8000 and one would fail. Always assign profiles to mutually exclusive services.
- **Using `runtime: nvidia` instead of `deploy.resources.reservations.devices`:** The runtime key is the legacy approach. Modern Compose uses the deploy specification.
- **Mixing `count` and `device_ids`:** Compose returns an error. Use one or the other.
- **Anonymous volumes:** Using bare paths without names causes data to be lost between `docker compose down` and `up`. Always use named volumes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Compose syntax validation | Custom YAML parser or manual inspection | `docker compose config --quiet` | Catches all schema errors, variable resolution, profile validation |
| GPU passthrough | Manual NVIDIA_VISIBLE_DEVICES + runtime config | `deploy.resources.reservations.devices` | Handles driver, capabilities, device selection properly |
| Air-gap test | Custom network isolation scripts | `docker run --network none` | Docker's none network driver is the standard isolation mechanism |
| Non-root verification | Parsing Dockerfile USER instruction | `docker run --rm IMAGE whoami` | Tests actual runtime behavior, not just Dockerfile declaration |
| Image metadata inspection | Parsing Dockerfile LABEL instructions | `docker inspect --format '{{json .Config.Labels}}' IMAGE` | Shows labels actually baked into the built image |

**Key insight:** Docker and Compose have built-in verification commands for every aspect of this phase. The verification checklist should use these native commands rather than any custom tooling.

## Common Pitfalls

### Pitfall 1: Volume Permission Denied for Non-Root User

**What goes wrong:** Container starts, tries to write to `/app/uploads` or `/app/processed`, gets permission denied because the named volume was created with root ownership.
**Why it happens:** Docker creates named volume directories as root:root. If the container runs as appuser (UID 1000), it cannot write.
**How to avoid:** The Dockerfiles already handle this: `RUN mkdir -p /app/uploads /app/processed /app/logs && chown -R appuser:appuser /app`. When Docker Compose creates a named volume for the first time and mounts it to a container path that already exists in the image with correct permissions, Docker populates the volume from the image contents (including ownership). This only works on FIRST mount -- if the volume already exists with different permissions, it won't be re-populated.
**Warning signs:** "Permission denied" errors in container logs when processing images.

### Pitfall 2: Forgetting `capabilities: [gpu]` in Device Reservation

**What goes wrong:** `docker compose --profile gpu up` fails with an error during service deployment.
**Why it happens:** The `capabilities` field is mandatory in `deploy.resources.reservations.devices`. Omitting it is a schema error.
**How to avoid:** Always include `capabilities: [gpu]` in the devices list.
**Warning signs:** Compose error at parse/deploy time, not at runtime.

### Pitfall 3: Using `version:` Key in Compose File

**What goes wrong:** Warning message printed: "`version` is obsolete." In some newer Compose versions, certain version strings cause errors.
**Why it happens:** Since Docker Compose v2.25.0 (March 2024), the version key is obsolete. The Compose Specification no longer uses it.
**How to avoid:** Simply omit the `version:` line entirely.
**Warning signs:** Warning output on any `docker compose` command.

### Pitfall 4: Both Services Starting When No Profile Specified

**What goes wrong:** Running `docker compose up` (without `--profile`) starts nothing, or starts only services without a profile attribute.
**Why it happens:** Services WITH a `profiles` attribute are NOT started unless their profile is active. Services WITHOUT `profiles` always start.
**How to avoid:** Both CPU and GPU services MUST have `profiles:` assigned. There should be no "always-on" services in this compose file since CPU and GPU are mutually exclusive.
**Warning signs:** `docker compose up` with no profile flag produces no running containers (correct behavior for this project).

### Pitfall 5: Build Context vs Dockerfile Location Mismatch

**What goes wrong:** Docker build fails with "COPY requirements.txt . failed: file not found".
**Why it happens:** The Dockerfiles live in `docker/` but COPY commands reference files relative to the build context. If build context is set to `docker/` instead of `.` (repo root), files like `requirements.txt` and `src/` are not in scope.
**How to avoid:** Set `context: .` (repo root) and `dockerfile: docker/Dockerfile.cpu` in the build configuration.
**Warning signs:** COPY failures during build.

### Pitfall 6: Air-Gap Test Fails Due to Lazy Model Loading

**What goes wrong:** `docker run --network none` succeeds at startup but the container fails when actually processing an image because a model tries to download at inference time rather than startup.
**Why it happens:** Some ML libraries (notably rembg/onnxruntime) download models lazily on first inference rather than at import time.
**How to avoid:** The Dockerfiles already bundle models into the image at build time. The test should not just check startup but verify the `/ready` endpoint returns successfully (models loaded). Since `--network none` blocks even the loopback healthcheck curl, test startup success via log output or a brief `sleep` + process check pattern.
**Warning signs:** Container starts but /ready returns false.

## Code Examples

Verified patterns from official sources:

### Complete docker-compose.yml Template

```yaml
# Source: Composite from Docker official docs
# https://docs.docker.com/compose/how-tos/profiles/
# https://docs.docker.com/compose/how-tos/gpu-support/

# No version: key (obsolete since Compose v2.25.0)

services:
  facecraft-cpu:
    profiles: [cpu]
    build:
      context: .
      dockerfile: docker/Dockerfile.cpu
    image: djok/facecraft:cpu
    ports:
      - "8000:8000"
    volumes:
      - uploads:/app/uploads
      - processed:/app/processed
    environment:
      # Server configuration
      FACECRAFT_HOST: "0.0.0.0"
      FACECRAFT_PORT: "8000"
      FACECRAFT_WORKERS: "1"
      # Device: forced to CPU
      FACECRAFT_DEVICE: "cpu"
      # Logging
      FACECRAFT_LOG_LEVEL: "INFO"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      start_period: 180s
      retries: 3
    restart: unless-stopped

  facecraft-gpu:
    profiles: [gpu]
    build:
      context: .
      dockerfile: docker/Dockerfile.gpu
    image: djok/facecraft:gpu
    ports:
      - "8000:8000"
    volumes:
      - uploads:/app/uploads
      - processed:/app/processed
    environment:
      # Server configuration
      FACECRAFT_HOST: "0.0.0.0"
      FACECRAFT_PORT: "8000"
      FACECRAFT_WORKERS: "1"
      # Device: auto-detect GPU
      FACECRAFT_DEVICE: "auto"
      # Logging
      FACECRAFT_LOG_LEVEL: "INFO"
      # NVIDIA runtime (set in Dockerfile, repeated for clarity)
      NVIDIA_VISIBLE_DEVICES: "all"
      NVIDIA_DRIVER_CAPABILITIES: "compute,utility"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      start_period: 180s
      retries: 3
    restart: unless-stopped

volumes:
  uploads:
  processed:
```

### Verification Commands

```bash
# 1. Build images (context is repo root, Dockerfiles in docker/)
docker compose --profile cpu build
docker compose --profile gpu build

# 2. Air-gap test: container starts with no network
docker run --rm --network none djok/facecraft:cpu \
  python -c "print('Container starts without internet')"

# 3. Non-root user verification
docker run --rm djok/facecraft:cpu whoami
# Expected output: appuser

# 4. CPU-only torch verification (from Phase 1)
docker run --rm djok/facecraft:cpu \
  python -c "import torch; print(torch.version.cuda)"
# Expected output: None

# 5. Validate compose syntax
docker compose config --quiet
# Exit code 0 = valid, non-zero = errors

# 6. Test CPU profile
docker compose --profile cpu up -d
curl -f http://localhost:8000/health
# Expected: {"status":"healthy"}
docker compose --profile cpu down

# 7. Test GPU profile (parse validation only if no GPU available)
docker compose --profile gpu config --quiet
# Validates GPU service syntax without needing actual GPU
```

### Healthcheck Endpoint Reference

The application exposes two health endpoints (from `src/facecraft/api/routes/health.py`):

- `/health` -- Basic liveness probe. Always returns `{"status": "healthy"}` if the process is running.
- `/ready` -- Readiness probe. Returns `{"ready": true, "models_loaded": true}` only when all models are loaded.

The Dockerfile HEALTHCHECK uses `/ready` (model-aware). The Compose healthcheck should use `/health` (liveness) for service orchestration since the Dockerfile already handles readiness internally. However, the success criteria say `/health` must return 200, which it will as soon as the FastAPI server is up.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `version: '3.8'` in compose file | No version key at all | Compose v2.25.0 (March 2024) | Warning if present, potential error with some version strings |
| `runtime: nvidia` for GPU | `deploy.resources.reservations.devices` | Compose Specification (2023+) | Cleaner syntax, native to compose spec, supports count/device selection |
| `docker-compose` (hyphenated CLI) | `docker compose` (plugin subcommand) | Docker Compose v2 (2022) | Old CLI deprecated; new is a Docker plugin |

**Deprecated/outdated:**
- `version:` key in docker-compose.yml: Obsolete, omit it entirely.
- `runtime: nvidia` in services: Legacy approach, use deploy.resources.reservations.devices.
- `docker-compose` command: Replaced by `docker compose` (no hyphen).

## Open Questions

1. **Air-gap test with `--network none` and healthcheck interaction**
   - What we know: `--network none` disables all networking including loopback for external connections. The container can still listen on localhost internally. The curl-based HEALTHCHECK inside the container targets `localhost:8000`, which should still work within the container's own network namespace.
   - What's unclear: Whether the HEALTHCHECK will pass inside a `--network none` container (loopback should still work, but the test needs to confirm startup success, not long-term health).
   - Recommendation: For the air-gap test, use a simple `python -c "..."` command or `timeout 30 python -m uvicorn ...` to test startup rather than relying on the healthcheck mechanism. The success criterion says "starts successfully" -- verify the process starts and does not crash, not that healthcheck passes.

2. **GPU profile testing without a GPU**
   - What we know: `docker compose --profile gpu config` validates syntax without starting services. The GPU image can be built on a machine without a GPU (CUDA base images don't require host GPU for build).
   - What's unclear: Whether `docker compose --profile gpu up` will error on a machine without NVIDIA Container Toolkit installed.
   - Recommendation: Separate build/syntax validation (works anywhere) from runtime testing (requires GPU host). The success criterion says "no compose errors on parse" -- use `docker compose config` for this.

## Sources

### Primary (HIGH confidence)
- [Docker Compose Profiles](https://docs.docker.com/compose/how-tos/profiles/) - Profile syntax, activation, dependency rules
- [Docker Compose GPU Support](https://docs.docker.com/compose/how-tos/gpu-support/) - deploy.resources.reservations.devices syntax, all examples
- [Compose Deploy Specification](https://docs.docker.com/reference/compose-file/deploy/) - Complete deploy spec including resources, devices fields
- [Compose Build Specification](https://docs.docker.com/reference/compose-file/build/) - Build context, dockerfile, args syntax
- [Compose Volumes Reference](https://docs.docker.com/reference/compose-file/volumes/) - Named volumes, top-level declarations, mount syntax
- [Docker None Network Driver](https://docs.docker.com/engine/network/drivers/none/) - Network isolation for air-gap testing
- [Compose Environment Variables](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/) - Env var syntax and precedence

### Secondary (MEDIUM confidence)
- [Docker Compose version key obsolete](https://github.com/docker/compose/issues/11628) - Confirmed obsolete since v2.25.0
- [Compose Named Volume Permissions](https://github.com/docker/compose/issues/3270) - Root ownership issue with named volumes
- [Compose Config Validation](https://www.baeldung.com/ops/docker-compose-yaml-file-check) - docker compose config usage

### Project Sources (HIGH confidence)
- Phase 1 Verification (`01-VERIFICATION.md`) - Confirmed all Dockerfiles hardened, ready for build
- `docker/Dockerfile.cpu` - CPU image with appuser, HEALTHCHECK /ready, CPU-only wheels
- `docker/Dockerfile.gpu` - GPU image with CUDA 12.1.0, HEALTHCHECK /ready
- `src/facecraft/api/routes/health.py` - /health and /ready endpoints
- `src/facecraft/core/config.py` - All FACECRAFT_* environment variables with defaults
- `.env.example` - Complete environment variable reference

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All from official Docker documentation
- Architecture: HIGH - Compose profiles, GPU deploy syntax, volumes all verified against official docs
- Pitfalls: HIGH - Volume permissions and version key issues confirmed in multiple official sources and GitHub issues
- Code examples: HIGH - Composite patterns verified against official docs, cross-referenced with actual project files

**Research date:** 2026-02-18
**Valid until:** 2026-03-18 (Docker Compose spec is stable; 30-day estimate)
