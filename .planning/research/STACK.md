# Stack Research

**Domain:** Docker packaging of Python ML/AI API for Docker Hub publication
**Researched:** 2026-02-18
**Confidence:** MEDIUM-HIGH (core Docker practices HIGH; version-specific ML library compat MEDIUM)

---

## Context

Facecraft is a working FastAPI API using PyTorch 2.0.1, dlib, rembg, and CodeFormer. The
existing Dockerfiles already implement a sound three-stage pattern. This research focuses on
**what to change, verify, and add** — not a from-scratch design. Recommendations are prescriptive
and address gaps in the current implementation.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Docker BuildKit | 1.x (builtin since Docker 23+) | Build engine | Default in modern Docker; enables cache mounts, bind mounts, ADD --checksum, and parallel stage execution. Never use legacy builder. |
| python:3.11-slim | 3.11-slim (Debian Bookworm) | CPU runtime base | Smallest Python image with glibc (not Alpine — dlib and OpenCV require glibc). Proven to work with PyTorch CPU wheels. |
| nvidia/cuda | 12.4.1-cudnn-runtime-ubuntu22.04 | GPU runtime base | CUDA 12.4 is the stable sweet spot: PyTorch 2.4+ supports it natively with cu124 wheels; newer than current 12.1 base which is approaching EOL. cudnn-runtime (not devel) keeps image size down. |
| PyTorch | 2.0.1 (CPU), 2.0.1+cu118 (GPU) | Deep learning inference | **Stay at 2.0.1 for now.** basicsr and realesrgan use `torchvision.transforms.functional_tensor` which was removed in torchvision 0.16+ (PyTorch 2.1+). Upgrading breaks CodeFormer without patching basicsr. Pin until basicsr is patched or replaced. |
| docker/build-push-action | v6 | GitHub Actions CI publishing | Current stable action for building and pushing to Docker Hub; supports BuildKit natively, cache-from/to, and multi-tag pushes. |
| docker/metadata-action | v5 | OCI label generation | Generates standard `org.opencontainers.image.*` labels from git tags/commits; Docker Hub reads these for description metadata. |

### Supporting Libraries (in Docker context)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| wget | system (apt) | Model download in model-downloader stage | Current approach works. `ADD --checksum` is better (see below) but requires knowing SHA256 upfront. Use wget + sha256sum verification as pragmatic alternative. |
| pip cache mount | BuildKit feature | Speed up repeated pip builds during development | `RUN --mount=type=cache,target=/root/.cache/pip` — do NOT use in CI where build environments are ephemeral; use `--no-cache-dir` in CI instead. |
| uv | 0.5+ | Fast pip replacement for wheel installs | Optional: uv is 10-100x faster than pip for dependency resolution. Worth adding in builder stage. Not yet mainstream for ML (LOW confidence on ecosystem readiness). |
| sha256sum | system (coreutils) | Model file integrity verification | Already available in slim images; verify every downloaded model file with a known hash embedded in the Dockerfile. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| docker buildx | Multi-platform builder | Already required for BuildKit; `docker buildx create --use` before builds |
| .dockerignore | Prevent bloating build context | Critical: exclude `__pycache__`, `.git`, `.env`, `tests/`, `*.pyc`, local model caches |
| docker buildx bake | Declarative multi-target builds | GA as of 2025; define `cpu` and `gpu` targets in a `docker-bake.hcl` file, build both with one command. Better than duplicate build scripts. |
| dive | Image layer analysis | Use `dive djok/facecraft:cpu` to inspect layer sizes and find waste before publishing |
| hadolint | Dockerfile linting | Catches anti-patterns (missing `--no-install-recommends`, unverified downloads, etc.) |

---

## Installation / Build Commands

```bash
# Enable BuildKit (required; default in Docker 23+, set explicitly for older environments)
export DOCKER_BUILDKIT=1

# Build CPU image
docker build \
  --file docker/Dockerfile.cpu \
  --tag djok/facecraft:cpu \
  --tag djok/facecraft:latest \
  --progress=plain \
  .

# Build GPU image
docker build \
  --file docker/Dockerfile.gpu \
  --tag djok/facecraft:gpu \
  --progress=plain \
  .

# Publish to Docker Hub
docker push djok/facecraft:cpu
docker push djok/facecraft:latest
docker push djok/facecraft:gpu

# With buildx bake (preferred for CI — builds CPU + GPU concurrently)
docker buildx bake --push
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| python:3.11-slim (CPU base) | python:3.11-alpine | Never for this stack — dlib, OpenCV, and PyTorch require glibc; Alpine uses musl libc and breaks C extension builds |
| nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 | Current nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 | CUDA 12.1 is still functional but outdated; 12.4 has broader PyTorch wheel support. Only stay on 12.1 if the deployment environment's driver version mandates it. |
| torch==2.0.1 (pinned) | torch>=2.4.0 | Use 2.4+ only after patching basicsr to fix the `torchvision.transforms.functional_tensor` import (change to `torchvision.transforms.functional`). Unpinned upgrade will break CodeFormer silently at runtime. |
| Multi-stage build (3 stages) | Single-stage build | Never use single-stage for ML images — you will inadvertently bundle cmake, build-essential, and pip caches into the final image, easily adding 1-2GB of waste. |
| wget + sha256sum verification | ADD --checksum | ADD --checksum is cleaner but requires computing SHA256 of target files upfront (one-time cost). Both are correct; ADD --checksum is the modern preferred approach. |
| docker/build-push-action v6 | Manual docker push in CI | Never manually push in CI — the action handles caching, provenance attestation, and multi-platform manifests correctly |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `--no-install-recommends` omitted in apt-get | Installs hundreds of MB of unnecessary packages (docs, debug tools, man pages) | Always use `apt-get install -y --no-install-recommends` |
| pip install without `--no-cache-dir` in production Dockerfile | Pip's download cache persists inside the image layer, adding unnecessary size | Use `--no-cache-dir` in all Dockerfile RUN steps; use `--mount=type=cache` only for local development builds |
| `latest` tag as only tag | Unpullable-by-version; breaks reproducibility; users can't pin to a known-good version | Tag with semantic version (`djok/facecraft:1.0.0`) AND convenience aliases (`:cpu`, `:gpu`) |
| Downloading models at runtime (entrypoint) | First-run latency is unacceptable (615MB download before API serves requests); fails in air-gapped environments | Bundle all models at build time (current approach is correct — keep it) |
| Installing PyTorch from default PyPI index for CPU image | Default PyPI torch wheels include CUDA stubs and are ~2.5GB; CPU-only wheels are ~600MB | Use `--index-url https://download.pytorch.org/whl/cpu` for CPU image |
| CUDA `devel` image as final production base | devel image includes full compiler toolchain, CUDA headers, and debug tools — adds ~4-5GB | Use `runtime` or `base` for final stage; use `devel` only in builder stage for compilation |
| Storing secrets/tokens as Docker LABELs | Labels are plaintext and visible to anyone who pulls the image | Use GitHub Actions secrets; never embed credentials in image metadata |
| Building amd64 image with QEMU emulation | QEMU is extremely slow for large ML builds; PyTorch compilation takes hours | Use native runners (amd64 host for amd64 image, arm64 host for arm64 image) if multi-arch is needed |

---

## Stack Patterns by Variant

**CPU variant (djok/facecraft:cpu):**
- Base: `python:3.11-slim`
- PyTorch install: `pip install torch==2.0.1 torchvision==0.15.2 --index-url https://download.pytorch.org/whl/cpu`
- rembg install: `rembg[cpu]` (uses onnxruntime CPU, not GPU)
- Target: users without GPU, standard cloud VMs, CI environments

**GPU variant (djok/facecraft:gpu):**
- Runtime base: `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04` (upgrade from current 12.1)
- Builder base: `nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04` (only in builder stage)
- PyTorch install: `pip install torch==2.0.1+cu118 torchvision==0.15.2+cu118 --extra-index-url https://download.pytorch.org/whl/cu118` (maintain cu118 wheels even on CUDA 12.4 host — CUDA is backward compatible)
- rembg install: `rembg[gpu]` + `onnxruntime-gpu`
- Target: users with NVIDIA GPU + nvidia-container-toolkit installed

**Note on CUDA forward compatibility:** PyTorch cu118 wheels run correctly on CUDA 12.4 hosts because CUDA is forward-compatible (host driver 12.4 supports containers compiled for 12.1/11.8). No need to recompile PyTorch.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| torch==2.0.1 | torchvision==0.15.2 | Strict pairing required — minor version mismatches cause cryptic import errors |
| torch==2.0.1+cu118 | nvidia/cuda:12.1 or 12.4 host | cu118 wheels run on CUDA 12.x hosts (forward compat); do not need cu121 wheels |
| basicsr==1.4.2 | torchvision<=0.15.x | basicsr imports `torchvision.transforms.functional_tensor` (removed in 0.16+); pinning torchvision to 0.15.2 avoids the breakage |
| rembg[cpu]>=2.0.50 | onnxruntime (CPU) | rembg[cpu] installs onnxruntime (CPU); rembg[gpu] installs onnxruntime-gpu — do not install both |
| dlib>=19.24.0 | python:3.11-slim | Requires cmake + build-essential at build time; runtime only needs libopenblas0 + liblapack3 |
| python:3.11-slim | Debian Bookworm (12) | Bookworm-based slim; libgl1, libglib2.0-0 must be explicitly installed for OpenCV headless |
| nvidia/cuda:12.4.1-cudnn-runtime | NVIDIA driver >= 525.60 | CUDA 12.4 requires driver 525.60.13+ on Linux; document this requirement in README |

---

## Critical Build Optimizations (Current Gaps)

The existing Dockerfiles are structurally sound but missing these optimizations:

### 1. Add model SHA256 verification

Current wget downloads have no integrity check — a corrupted or MITM'd download would silently produce a broken image.

```dockerfile
# In model-downloader stage — after wget:
RUN sha256sum -c <<'EOF'
a4e6e2e4d7b882dff5ffdaa13aa4d990cbedbdc25c8b27ac5dbf3cf9d10aa50b  shape_predictor_68_face_landmarks.dat
# (get actual hash by: sha256sum shape_predictor_68_face_landmarks.dat)
EOF
```

Or use ADD --checksum (preferred, BuildKit-native):
```dockerfile
ADD --checksum=sha256:<known-hash> \
    https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth \
    /models/codeformer/codeformer.pth
```

### 2. Use CPU-specific PyTorch index for CPU image

Current requirements.txt uses `torch==2.0.1` which installs from default PyPI — this bundles CUDA stubs and is larger than necessary.

```dockerfile
# In CPU builder stage:
RUN pip wheel --no-cache-dir --wheel-dir /wheels \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt
```

Or pin CPU wheels explicitly in requirements.txt:
```
--index-url https://download.pytorch.org/whl/cpu
torch==2.0.1+cpu
torchvision==0.15.2+cpu
```

### 3. Add OCI standard labels

```dockerfile
LABEL org.opencontainers.image.title="Facecraft"
LABEL org.opencontainers.image.description="AI Portrait Processing API"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.source="https://github.com/djok/facecraft"
LABEL org.opencontainers.image.licenses="MIT"
```

### 4. Add .dockerignore

Critical to prevent `src/__pycache__`, local model caches, `.git/`, test fixtures from inflating build context.

```
**/__pycache__
**/*.pyc
**/*.pyo
.git
.env
*.egg-info
dist/
build/
tests/
*.ipynb
research/
.planning/
```

### 5. Pin base image by digest in production CI

For reproducible published images, pin base images to SHA256 digests:
```dockerfile
FROM python:3.11-slim@sha256:<digest> AS model-downloader
```
Prevents silent base image changes from affecting published images.

---

## CI/CD: GitHub Actions for Docker Hub Publishing

The standard 2025 workflow for publishing to Docker Hub:

```yaml
# .github/workflows/docker-publish.yml
name: Publish Docker Images

on:
  push:
    tags: ['v*']

jobs:
  build-cpu:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Docker meta
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: djok/facecraft
          tags: |
            type=semver,pattern={{version}},suffix=-cpu
            type=raw,value=cpu

      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ vars.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push CPU
        uses: docker/build-push-action@v6
        with:
          context: .
          file: docker/Dockerfile.cpu
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  build-gpu:
    runs-on: ubuntu-latest
    steps:
      # ... same pattern with Dockerfile.gpu and gpu tag suffix
```

**Key decisions:**
- `docker/metadata-action@v5` generates OCI-compliant labels automatically from git tags
- `type=gha` cache (GitHub Actions Cache) is the correct cache backend for ephemeral runners
- CPU and GPU jobs run in parallel (separate jobs, not sequential steps)
- `DOCKERHUB_TOKEN` is a Docker Hub Personal Access Token (PAT), not your password

---

## Sources

- [Docker Multi-stage Builds — Official Docs](https://docs.docker.com/build/building/multi-stage/) — Architecture pattern; HIGH confidence
- [Docker Build Best Practices — Official Docs](https://docs.docker.com/build/building/best-practices/) — Layer ordering, apt cleanup; HIGH confidence
- [Docker Cache Optimization — Official Docs](https://docs.docker.com/build/cache/optimize/) — Cache mounts, bind mounts; HIGH confidence
- [Dockerfile ADD --checksum Reference](https://docs.docker.com/reference/dockerfile/#add) — SHA256 verification syntax; HIGH confidence
- [Docker BuildKit GitHub](https://github.com/moby/buildkit) — Cache mount behavior details; HIGH confidence
- [Docker Bake — Official Docs](https://docs.docker.com/build/bake/) — Multi-target declarative builds; HIGH confidence (GA 2025)
- [GitHub Actions Docker Build+Push Action v6](https://github.com/docker/build-push-action) — CI publishing standard; HIGH confidence
- [NVIDIA NGC CUDA Catalog](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/cuda) — Current CUDA image tags; MEDIUM confidence (verified via NGC)
- [Optimizing PyTorch Docker Images — 60% reduction](https://mveg.es/posts/optimizing-pytorch-docker-images-cut-size-by-60percent/) — CPU index URL + no-cache-dir; MEDIUM confidence (blog, verified against PyTorch docs)
- [basicsr torchvision.functional_tensor breakage — GitHub Issue #711](https://github.com/XPixelGroup/BasicSR/issues/711) — PyTorch version pinning rationale; HIGH confidence (multiple reporters, confirmed)
- [Real-ESRGAN torchvision compatibility issue #765](https://github.com/xinntao/Real-ESRGAN/issues/765) — Confirms torch==2.0.1 + torchvision==0.15.2 as safe pairing; HIGH confidence

---

*Stack research for: Facecraft Docker packaging milestone*
*Researched: 2026-02-18*
