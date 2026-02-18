# Phase 1: Dockerfile Hardening - Research

**Researched:** 2026-02-18
**Domain:** Docker image hardening (checksums, OCI labels, CPU wheels, HEALTHCHECK)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Silent by default -- no output during successful checksum verification
- Output only on failure (checksum mismatch or download error)
- No summary line on success -- Unix-style silence when everything is OK
- SHA256 hashes stored inline in each Dockerfile as ARG values
- Hashes duplicated in both Dockerfile.cpu and Dockerfile.gpu (each file is self-contained)
- A `make update-checksums` Makefile target to automate hash updates: downloads models, computes SHA256, patches both Dockerfiles
- License: MIT
- Source URL: https://github.com/djok/facecraft
- `.version` and `.description` labels included

### Claude's Discretion
- Error message format on checksum failure (expected vs actual hash detail level)
- Download retry behavior on network failure
- Version scheme (semver vs calver)
- Description text content
- Exact OCI label wording

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

## Summary

Phase 1 patches five concrete gaps in the existing Dockerfiles. The codebase already has a well-structured multi-stage build for both CPU and GPU images. The gaps are: (1) CPU Dockerfile does not use CPU-only PyTorch wheels, pulling CUDA-bundled torch instead; (2) model downloads have no integrity verification; (3) labels use legacy `LABEL maintainer` instead of OCI standard `org.opencontainers.image.*`; (4) HEALTHCHECK targets `/health` with 120s start-period instead of `/ready` with 180s; (5) `.dockerignore` exists but is missing `.planning/` exclusion.

**Primary recommendation:** Apply targeted patches to both Dockerfiles -- no structural changes needed. The multi-stage build architecture is sound; only the five specific gaps need closing.

## Standard Stack

### Core (Already in Place)
| Component | Current | Purpose | Status |
|-----------|---------|---------|--------|
| python:3.11-slim | 3.11-slim | CPU base image | Keep |
| nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 | 12.1.0 | GPU runtime base | **Keep** (see findings) |
| torch==2.0.1 | 2.0.1 | Deep learning | Pinned (basicsr constraint) |
| torchvision==0.15.2 | 0.15.2 | Vision transforms | Pinned (basicsr constraint) |
| sha256sum | coreutils | Checksum verification | Add to model-downloader |

### Key Tools for This Phase
| Tool | Purpose | Why |
|------|---------|-----|
| `sha256sum` | Verify model checksums inline | Available in coreutils, pre-installed in python:3.11-slim |
| `ARG` | Store expected hashes | Dockerfile-native, self-contained per user decision |
| `LABEL` (OCI) | Image metadata | Docker/OCI standard |
| `HEALTHCHECK` | Container health probe | Docker built-in |

## Architecture Patterns

### Pattern 1: CPU-Only PyTorch Wheel Installation
**What:** Use `--index-url https://download.pytorch.org/whl/cpu` to install torch==2.0.1+cpu and torchvision==0.15.2+cpu
**Confidence:** HIGH (verified against PyTorch official release matrix)

In the CPU Dockerfile builder stage, change:
```dockerfile
# BEFORE (pulls CUDA-bundled wheel from PyPI -- ~2GB wasted)
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# AFTER (pulls CPU-only wheel -- ~200MB)
RUN pip wheel --no-cache-dir --wheel-dir /wheels \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt
```

The `requirements.txt` already pins `torch==2.0.1` and `torchvision==0.15.2`. The `--extra-index-url` flag adds the CPU wheel index as an additional source. pip resolves the CPU-only versions (`2.0.1+cpu`, `0.15.2+cpu`) from that index.

**Verification:** After build, run: `python -c "import torch; print(torch.version.cuda)"` -- must print `None`.

### Pattern 2: SHA256 Checksum Verification (Inline ARG)
**What:** Store expected hashes as `ARG` values, verify after each download with `sha256sum`
**Confidence:** HIGH (standard Unix pattern)

```dockerfile
# Declare expected hashes as ARGs (self-contained in each Dockerfile)
ARG SHAPE_PREDICTOR_SHA256=<hash>
ARG CODEFORMER_SHA256=<hash>
ARG U2NET_SHA256=<hash>

# Download + verify pattern (silent on success, loud on failure)
RUN wget -q http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2 \
    && bunzip2 shape_predictor_68_face_landmarks.dat.bz2 \
    && echo "${SHAPE_PREDICTOR_SHA256}  shape_predictor_68_face_landmarks.dat" | sha256sum -c --quiet
```

`sha256sum -c --quiet` exits 0 silently on match, exits non-zero with error message on mismatch -- exactly matching the "silent on success, loud on failure" decision.

**Note:** The actual SHA256 hashes are not known yet. They must be computed from live downloads during plan execution. This is a known blocker documented in STATE.md.

### Pattern 3: OCI Standard Labels
**What:** Replace legacy `LABEL maintainer` with `org.opencontainers.image.*` labels
**Confidence:** HIGH (OCI Image Spec v1.1)

```dockerfile
LABEL org.opencontainers.image.source="https://github.com/djok/facecraft" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.description="Facecraft - AI Portrait Processing API (CPU)" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.title="facecraft" \
      org.opencontainers.image.vendor="OBVT Toolbox"
```

The full set of OCI pre-defined keys (from specs.opencontainers.org):
- `org.opencontainers.image.created` -- RFC 3339 datetime
- `org.opencontainers.image.authors` -- contact details
- `org.opencontainers.image.url` -- URL to find more info
- `org.opencontainers.image.documentation` -- URL for docs
- `org.opencontainers.image.source` -- URL to source code
- `org.opencontainers.image.version` -- version of packaged software
- `org.opencontainers.image.revision` -- source control revision
- `org.opencontainers.image.vendor` -- distributing entity
- `org.opencontainers.image.licenses` -- SPDX License Expression
- `org.opencontainers.image.title` -- human-readable title
- `org.opencontainers.image.description` -- human-readable description

Required by project decisions: `.source`, `.version`, `.description`, `.licenses`. The `.title` and `.vendor` are optional additions.

### Pattern 4: HEALTHCHECK Configuration
**What:** Target `/ready` endpoint with 180s start-period
**Confidence:** HIGH (existing endpoint confirmed in codebase)

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD curl -f http://localhost:8000/ready || exit 1
```

Current Dockerfiles use `/health` with `--start-period=120s`. The `/ready` endpoint (confirmed at `src/facecraft/api/routes/health.py:33`) checks that models are actually loaded (`processor.background_remover is not None and processor.face_detector is not None`), making it superior to `/health` which only confirms the process is running.

The 180s start-period gives adequate time for model loading (dlib shape predictor + CodeFormer + u2net_human_seg).

### Pattern 5: .dockerignore Update
**What:** Add `.planning/` to existing .dockerignore
**Confidence:** HIGH (trivial file edit)

The existing `.dockerignore` already excludes `.git`, `tests`, `__pycache__`, `.env`. It is missing `.planning/` which must be added per requirements (DOCK-04).

## GPU Base Image: CUDA Version Decision

### Critical Finding: CUDA 12.4 Upgrade is Incompatible

**Confidence:** HIGH

The project STATE.md records a decision to upgrade the GPU base to `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04`. However, research reveals this is **problematic**:

1. **PyTorch 2.0.1 only has cu117 and cu118 wheels** -- there are no cu121/cu124 wheels for this version
2. **basicsr==1.4.2 breaks on torchvision 0.16+**, so upgrading PyTorch is not an option
3. PyTorch bundles its own CUDA runtime inside the wheel, so cu118 wheels *can* run inside a CUDA 12.x container
4. However, the builder stage (`nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04`) is used for compiling dlib and other C extensions -- changing this to 12.4 should be safe since we're not compiling CUDA code

**Recommendation:** Keep `cu118` PyTorch wheels. The base image upgrade from 12.1.0 to 12.4.1 is technically possible (PyTorch bundles its own CUDA runtime), but introduces unnecessary risk for zero benefit since torch 2.0.1+cu118 already works. **Keep the existing CUDA 12.1 base images** unless there's a specific driver requirement.

This should be flagged as an open question for the planner to handle.

### Verified GPU Image Tags
If upgrade is desired anyway:
- Builder: `nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04` (confirmed on Docker Hub)
- Runtime: `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04` (confirmed on Docker Hub)

Note the naming convention changed: CUDA 12.4+ uses `-cudnn-` (no version number) instead of `-cudnn8-`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Checksum verification | Custom script | `sha256sum -c --quiet` | POSIX standard, silent-on-success built-in |
| Model hash updates | Manual copy-paste | `make update-checksums` target | User decision: Makefile target for automation |
| CPU wheel selection | Manual URL construction | `--extra-index-url .../whl/cpu` | pip resolves correct platform automatically |

## Common Pitfalls

### Pitfall 1: --index-url vs --extra-index-url for CPU Wheels
**What goes wrong:** Using `--index-url` replaces the default PyPI index entirely, so non-PyTorch packages fail to resolve
**Why it happens:** PyTorch docs sometimes show `--index-url` which works for `pip install` of torch alone, but breaks `pip wheel -r requirements.txt` where other packages need PyPI
**How to avoid:** Use `--extra-index-url` in the builder stage where requirements.txt includes non-PyTorch packages
**Warning signs:** Build fails with "No matching distribution found" for packages like `fastapi` or `dlib`

### Pitfall 2: Checksum of Compressed vs Uncompressed Files
**What goes wrong:** Computing hash of `.bz2` file but verifying against uncompressed `.dat` file (or vice versa)
**Why it happens:** The dlib shape predictor is downloaded as `.bz2` and decompressed
**How to avoid:** Compute and verify the hash of the **uncompressed** `.dat` file (after `bunzip2`), since that's what gets copied to the final image
**Warning signs:** Checksum always fails despite correct download

### Pitfall 3: u2net Model Download Path
**What goes wrong:** The u2net model is not downloaded via `wget` -- it's cached by `rembg` Python package during `pip install` + `python -c "from rembg..."`
**Why it happens:** rembg downloads to `~/.u2net/` automatically; there's no direct URL to wget
**How to avoid:** Verify the cached model file at `/root/.u2net/u2net_human_seg.onnx` after the Python download step
**Warning signs:** Trying to wget a u2net URL that doesn't exist or changes

### Pitfall 4: HEALTHCHECK During Build
**What goes wrong:** Nothing -- HEALTHCHECK only runs at container runtime, not during `docker build`
**Why it happens:** Confusion between build-time and run-time concerns
**How to avoid:** Understand HEALTHCHECK is a runtime instruction; `curl` must be installed in the runtime stage (already is)

### Pitfall 5: ARG Scope in Multi-Stage Builds
**What goes wrong:** ARGs declared before the first FROM are not available in subsequent stages
**Why it happens:** Each FROM starts a new build stage with its own scope
**How to avoid:** Declare `ARG` values inside the stage that needs them (model-downloader stage)
**Warning signs:** Empty hash variable causing `sha256sum` to always pass

## Code Examples

### Complete Checksum Verification Pattern (All 3 Models)

```dockerfile
# In model-downloader stage
ARG SHAPE_PREDICTOR_SHA256=<to_be_computed>
ARG CODEFORMER_SHA256=<to_be_computed>
ARG U2NET_SHA256=<to_be_computed>

# dlib shape predictor
RUN wget -q http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2 \
    && bunzip2 shape_predictor_68_face_landmarks.dat.bz2 \
    && echo "${SHAPE_PREDICTOR_SHA256}  shape_predictor_68_face_landmarks.dat" | sha256sum -c --quiet

# CodeFormer
RUN mkdir -p codeformer \
    && wget -q https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth \
       -O codeformer/codeformer.pth \
    && echo "${CODEFORMER_SHA256}  codeformer/codeformer.pth" | sha256sum -c --quiet

# u2net (downloaded via rembg, then verified)
RUN pip install --no-cache-dir "rembg[cpu]" \
    && python -c "from rembg import new_session; new_session('u2net_human_seg')" \
    && echo "${U2NET_SHA256}  /root/.u2net/u2net_human_seg.onnx" | sha256sum -c --quiet \
    && cp -r /root/.u2net /models/u2net
```

### Makefile update-checksums Target

```makefile
.PHONY: update-checksums
update-checksums:
	@echo "Downloading models and computing SHA256 hashes..."
	@# Shape predictor
	@wget -q http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2 -O /tmp/sp.bz2
	@bunzip2 -f /tmp/sp.bz2
	@SHAPE_HASH=$$(sha256sum /tmp/sp | awk '{print $$1}') && \
		sed -i "s/^ARG SHAPE_PREDICTOR_SHA256=.*/ARG SHAPE_PREDICTOR_SHA256=$$SHAPE_HASH/" \
			docker/Dockerfile.cpu docker/Dockerfile.gpu
	@# CodeFormer
	@wget -q https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth -O /tmp/cf.pth
	@CF_HASH=$$(sha256sum /tmp/cf.pth | awk '{print $$1}') && \
		sed -i "s/^ARG CODEFORMER_SHA256=.*/ARG CODEFORMER_SHA256=$$CF_HASH/" \
			docker/Dockerfile.cpu docker/Dockerfile.gpu
	@# u2net (requires Python with rembg)
	@pip install --quiet "rembg[cpu]" && \
		python -c "from rembg import new_session; new_session('u2net_human_seg')" && \
		U2_HASH=$$(sha256sum ~/.u2net/u2net_human_seg.onnx | awk '{print $$1}') && \
		sed -i "s/^ARG U2NET_SHA256=.*/ARG U2NET_SHA256=$$U2_HASH/" \
			docker/Dockerfile.cpu docker/Dockerfile.gpu
	@rm -f /tmp/sp /tmp/cf.pth
	@echo "Checksums updated in both Dockerfiles."
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `LABEL maintainer` | `org.opencontainers.image.*` | OCI Image Spec v1.0 (2017) | Legacy label still works but not standard |
| `/health` liveness only | `/ready` readiness check | Best practice | Model-aware health check |
| No checksum verification | `sha256sum -c --quiet` | Always recommended | Integrity assurance |
| `--index-url` for CPU torch | `--extra-index-url` | pip behavior | Preserves PyPI access for other packages |

**Deprecated/outdated:**
- `LABEL maintainer="..."` -- replaced by `org.opencontainers.image.authors`
- `nvidia/cuda:*-cudnn8-*` naming -- CUDA 12.4+ changed to `-cudnn-` (no version number)

## Open Questions

1. **CUDA Base Image Upgrade**
   - What we know: State decision says upgrade to CUDA 12.4.1; PyTorch 2.0.1 only has cu118 wheels; cu118 wheels work inside CUDA 12.x containers because PyTorch bundles its own CUDA runtime
   - What's unclear: Whether there's a concrete benefit to upgrading the base image when the PyTorch CUDA runtime is self-contained
   - Recommendation: Keep CUDA 12.1.0 base images for Phase 1 (safest). Revisit base image upgrade in a future phase if/when PyTorch is upgraded

2. **Actual SHA256 Hashes**
   - What we know: Hashes must be computed from live model downloads
   - What's unclear: Whether model files at these URLs are stable (same hash every download) or rebuilt periodically
   - Recommendation: Download and compute during plan execution. The `make update-checksums` target handles future updates

3. **u2net Model File Path**
   - What we know: rembg caches to `~/.u2net/u2net_human_seg.onnx`
   - What's unclear: Exact filename may vary by rembg version
   - Recommendation: Verify the exact path during execution; the checksum verification step will catch any path issues

## Sources

### Primary (HIGH confidence)
- OCI Image Spec Annotations: https://specs.opencontainers.org/image-spec/annotations/
- PyTorch Previous Versions: https://pytorch.org/get-started/previous-versions/
- Docker Hub nvidia/cuda tags: https://hub.docker.com/r/nvidia/cuda/tags
- Facecraft source code: `docker/Dockerfile.cpu`, `docker/Dockerfile.gpu`, `src/facecraft/api/routes/health.py`

### Secondary (MEDIUM confidence)
- Docker HEALTHCHECK reference: https://docs.docker.com/reference/dockerfile/
- PyTorch CPU wheel index: https://download.pytorch.org/whl/cpu
- NVIDIA CUDA 12.4.1 image layers: https://hub.docker.com/layers/nvidia/cuda/12.4.1-cudnn-runtime-ubuntu22.04/

### Tertiary (LOW confidence)
- PyTorch cu118 forward compatibility on CUDA 12.x: Based on community reports that PyTorch bundles its own CUDA runtime. Should be validated during build.

## Metadata

**Confidence breakdown:**
- CPU wheel installation: HIGH -- verified against official PyTorch release matrix
- SHA256 verification pattern: HIGH -- standard POSIX/coreutils
- OCI labels: HIGH -- from official OCI specification
- HEALTHCHECK: HIGH -- endpoint confirmed in source code
- CUDA base image compatibility: MEDIUM -- forward compatibility is documented but not tested for this specific version combo
- .dockerignore: HIGH -- trivial addition to existing file

**Research date:** 2026-02-18
**Valid until:** 2026-03-18 (stable domain, no fast-moving dependencies)
