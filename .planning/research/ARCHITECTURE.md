# Architecture Research

**Domain:** Docker packaging of ML inference API (CPU + GPU variants with bundled models)
**Researched:** 2026-02-18
**Confidence:** HIGH (existing Dockerfiles verified, patterns confirmed via official Docker docs)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BUILD PIPELINE                               │
│                                                                     │
│  ┌──────────────────────┐     ┌──────────────────────┐             │
│  │   model-downloader   │     │   model-downloader   │             │
│  │  (python:3.11-slim)  │     │  (python:3.11-slim)  │             │
│  │                      │     │                      │             │
│  │  wget dlib .dat.bz2  │     │  wget dlib .dat.bz2  │             │
│  │  wget codeformer.pth │     │  wget codeformer.pth │             │
│  │  rembg u2net cache   │     │  rembg u2net cache   │             │
│  └──────────┬───────────┘     └──────────┬───────────┘             │
│             │ COPY --from                │ COPY --from             │
│  ┌──────────▼───────────┐     ┌──────────▼───────────┐             │
│  │       builder        │     │       builder        │             │
│  │  (python:3.11-slim)  │     │  (cuda:12.1-devel)   │             │
│  │                      │     │                      │             │
│  │  cmake + dlib build  │     │  cmake + dlib build  │             │
│  │  pip wheel build     │     │  pip wheel (GPU pkgs)│             │
│  │  /wheels/*.whl       │     │  /wheels/*.whl       │             │
│  └──────────┬───────────┘     └──────────┬───────────┘             │
│             │ COPY --from                │ COPY --from             │
│  ┌──────────▼───────────┐     ┌──────────▼───────────┐             │
│  │  production (CPU)    │     │  production (GPU)    │             │
│  │  python:3.11-slim    │     │  cuda:12.1-runtime   │             │
│  │                      │     │                      │             │
│  │  /app/models/ (615MB)│     │  /app/models/ (615MB)│             │
│  │  /app/src/ (app code)│     │  /app/src/ (app code)│             │
│  │  appuser (non-root)  │     │  appuser (non-root)  │             │
│  │  HEALTHCHECK curl    │     │  HEALTHCHECK curl    │             │
│  └──────────────────────┘     └──────────────────────┘             │
│      djok/facecraft:cpu           djok/facecraft:gpu               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                  docker-compose.yml
                              │
          ┌───────────────────┴──────────────────┐
          │                                      │
┌─────────▼───────────┐              ┌───────────▼──────────┐
│  profile: cpu        │              │  profile: gpu        │
│  image: :cpu         │              │  image: :gpu         │
│  port: 8000:8000     │              │  port: 8000:8000     │
│  env: DEVICE=cpu     │              │  env: DEVICE=cuda    │
│  healthcheck         │              │  deploy.resources    │
│                      │              │    nvidia GPU caps   │
└──────────────────────┘              └──────────────────────┘
          │                                      │
          └──────────────┬───────────────────────┘
                         │
              ┌──────────▼──────────┐
              │   FastAPI app       │
              │   :8000             │
              │                     │
              │  /health            │
              │  /ready             │
              │  /api/v1/process    │
              │  /api/v1/process/   │
              │    quick            │
              │    batch            │
              └─────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| model-downloader stage | Download and cache all ML model artifacts at build time | python:3.11-slim with wget/bzip2; outputs /models/ with .dat, .pth, u2net dir |
| builder stage (CPU) | Compile C extensions (dlib) and pre-build Python wheels | python:3.11-slim + cmake + build-essential; outputs /wheels/*.whl |
| builder stage (GPU) | Same as CPU builder but against CUDA devel image for GPU-linked packages | nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04 + Python 3.11; outputs /wheels/*.whl |
| production stage (CPU) | Minimal runtime image with models and app | python:3.11-slim + runtime libs only; no build tools |
| production stage (GPU) | Minimal CUDA runtime image with models and app | nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04; smaller than devel |
| docker-compose.yml | Orchestrate CPU/GPU variants as named profiles | Single file, two services with profiles: [cpu] and profiles: [gpu] |
| .dockerignore | Exclude build artifacts, models, env files from build context | Excludes .git, __pycache__, models/, .env, tests/ |
| README.md | English quickstart with one-liner run commands | docker pull + docker run + environment variable reference |

## Recommended Project Structure

```
facecraft/
├── docker/
│   ├── Dockerfile.cpu          # 3-stage: model-downloader → builder → production
│   └── Dockerfile.gpu          # 3-stage: model-downloader → cuda-builder → cuda-production
├── docker-compose.yml          # profiles: cpu | gpu, single file for both variants
├── .dockerignore               # exclude models/, .env, tests/, __pycache__, .git
├── README.md                   # English quickstart, API reference, configuration
├── requirements.txt            # CPU Python dependencies (pinned)
├── requirements-gpu.txt        # GPU delta requirements (torch+cu118, onnxruntime-gpu)
└── src/
    └── facecraft/              # application code (unchanged from existing)
```

### Structure Rationale

- **docker/ subdirectory:** Keeps Dockerfiles out of repo root. Both files share same model-downloader stage logic — opportunity to extract to a shared include, but two separate files is simpler and explicit for CPU vs GPU divergence.
- **docker-compose.yml at root:** Standard placement. Users expect `docker-compose up` at repo root.
- **Single docker-compose.yml with profiles:** Avoids docker-compose.cpu.yml / docker-compose.gpu.yml split. One file, user selects variant with `--profile cpu` or `--profile gpu`. This is the current Docker Compose best practice (confirmed via official docs).
- **requirements-gpu.txt as delta:** Contains only the GPU-specific overrides (torch+cu118, onnxruntime-gpu). The builder stage installs both requirements.txt and requirements-gpu.txt. CPU builder installs only requirements.txt.

## Architectural Patterns

### Pattern 1: Shared model-downloader Stage

**What:** Both CPU and GPU Dockerfiles use an identical `model-downloader` stage based on `python:3.11-slim`. This stage downloads all three models (dlib .dat, CodeFormer .pth, u2net via rembg) and stores them under `/models/`. The production stages copy from this stage with `COPY --from=model-downloader`.

**When to use:** Always — model downloads are network-dependent and slow. An isolated stage means Docker layer cache prevents re-downloading on code changes. Build times drop dramatically after first build.

**Trade-offs:** The model-downloader stage adds ~615MB to the build graph but nothing to the final image size (Docker discards non-final stages). The stage is identical between CPU and GPU builds, so a future optimization could use a shared base or BuildKit cache mount.

**Example:**
```dockerfile
# Stage 1: Download all models once
FROM python:3.11-slim AS model-downloader
WORKDIR /models

RUN apt-get update && apt-get install -y --no-install-recommends wget bzip2 \
    && rm -rf /var/lib/apt/lists/*

# Each model in its own RUN = separate cache layer
# Changing one model doesn't invalidate others
RUN wget -q http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2 \
    && bunzip2 shape_predictor_68_face_landmarks.dat.bz2

RUN mkdir -p codeformer \
    && wget -q https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth \
       -O codeformer/codeformer.pth

RUN pip install --no-cache-dir "rembg[cpu]" \
    && python -c "from rembg import new_session; new_session('u2net_human_seg')" \
    && cp -r /root/.u2net /models/u2net

# Stage 3: Production — consume from model-downloader
COPY --from=model-downloader /models/shape_predictor_68_face_landmarks.dat /app/models/
COPY --from=model-downloader /models/codeformer/ /app/models/codeformer/
COPY --from=model-downloader /models/u2net /home/appuser/.u2net
```

### Pattern 2: Builder Stage for Compiled Dependencies

**What:** A dedicated `builder` stage installs cmake, build-essential, and other compile-time tools needed to build dlib and other C extensions. It outputs pre-built Python wheels to `/wheels/`. The production stage copies `/wheels/` and installs with pip, then deletes the wheels. This keeps the production image free of compilers.

**When to use:** Any time the stack includes C-compiled Python packages (dlib, numpy, opencv). Without this, cmake and gcc would be present in the production image, adding 200-400MB.

**Trade-offs:** Builder stage uses the CUDA devel image for GPU (larger than runtime) but this only affects build time, not image size. The production GPU image uses the smaller `runtime` variant.

**Example:**
```dockerfile
# CPU Builder
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake build-essential libopenblas-dev liblapack-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# GPU Builder — diverges here: different base, additional requirements
FROM nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04 AS builder
# ... install python3.11, cmake, build tools ...
COPY requirements.txt requirements-gpu.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt -r requirements-gpu.txt

# Production — install from wheels, then clean up
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
```

### Pattern 3: docker-compose Profiles for CPU/GPU Selection

**What:** A single `docker-compose.yml` defines two services (`facecraft-cpu` and `facecraft-gpu`), each assigned to a named profile. Users activate one with `docker compose --profile cpu up` or `docker compose --profile gpu up`. The GPU service includes `deploy.resources.reservations.devices` with `capabilities: [gpu]`.

**When to use:** When shipping both CPU and GPU variants and wanting a single config file. Profiles are the official Docker Compose mechanism for conditional service activation.

**Trade-offs:** Users must know to specify `--profile`. Without `--profile`, neither service starts (services with profiles are excluded by default). Document this clearly in README.

**Example:**
```yaml
services:
  facecraft-cpu:
    profiles: [cpu]
    image: djok/facecraft:cpu
    ports:
      - "8000:8000"
    environment:
      FACECRAFT_DEVICE: cpu
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      start_period: 120s
      retries: 3

  facecraft-gpu:
    profiles: [gpu]
    image: djok/facecraft:gpu
    ports:
      - "8000:8000"
    environment:
      FACECRAFT_DEVICE: cuda
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      start_period: 120s
      retries: 3
```

## Data Flow

### Build-Time Data Flow

```
Internet (dlib.net, GitHub releases, PyPI)
    │
    ▼
model-downloader stage (python:3.11-slim)
    │  wget shape_predictor_68_face_landmarks.dat.bz2 → decompress
    │  wget codeformer.pth
    │  pip install rembg → python trigger → u2net_human_seg downloaded to /root/.u2net
    │  cp /root/.u2net → /models/u2net
    ▼
/models/
    ├── shape_predictor_68_face_landmarks.dat  (95MB)
    ├── codeformer/codeformer.pth              (350MB)
    └── u2net/u2net_human_seg.onnx             (170MB)
    │
    │  COPY --from=model-downloader
    ▼
production stage /app/models/ and /home/appuser/.u2net
    │
    │  +
    ▼
builder stage → /wheels/*.whl
    │
    │  COPY --from=builder
    ▼
production stage: pip install /wheels/* → rm -rf /wheels
    │
    │  +
    ▼
COPY src/ /app/src/
    │
    ▼
Final image pushed to djok/facecraft:cpu or djok/facecraft:gpu
```

### Runtime Data Flow

```
User: docker run -p 8000:8000 djok/facecraft:cpu
    │
    ▼
Container starts as appuser (non-root, uid 1000)
    │
    ▼
uvicorn facecraft.main:app --host 0.0.0.0 --port 8000
    │
    ▼
FastAPI lifespan startup:
    - PhotoProcessor initialized
    - Models loaded from /app/models/ (dlib, CodeFormer)
    - rembg loads u2net from /home/appuser/.u2net/
    - Device auto-detected (cpu or cuda)
    │
    ▼
HTTP requests: POST /api/v1/process → processing pipeline → response
```

### Key Data Flows

1. **Model path at build time:** `/models/` in model-downloader stage → `COPY --from` → `/app/models/` in production. The u2net model goes to `/home/appuser/.u2net` because rembg looks for it in the user's home directory, not a configurable path.

2. **Model path at runtime:** `FACECRAFT_MODELS_DIR=/app/models` env var → `settings.models_dir` → `FaceDetector`, `FaceEnhancer` load from `/app/models/`. `BackgroundRemover` via rembg reads from `/home/appuser/.u2net/` (rembg default).

3. **Build cache invalidation order:** model-downloader (invalidated only if URLs or install commands change) → builder (invalidated if requirements.txt changes) → production (invalidated if source code or Dockerfile changes). Most rebuilds hit only the production stage.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single developer or small team | Current architecture is correct — single container per deployment, uvicorn with 1 worker |
| 10-100 concurrent users | Increase FACECRAFT_WORKERS to 2-4 (Gunicorn + uvicorn workers), add nginx reverse proxy |
| Production multi-instance | Add container orchestration (Docker Swarm or Kubernetes), shared volume or S3 for processed outputs, separate model storage from app image |

### Scaling Priorities

1. **First bottleneck:** Model inference is CPU/GPU-bound and single-threaded in current implementation. Increase worker count first. 4 workers on a 4-core CPU covers most workloads.
2. **Second bottleneck:** Processed file storage grows unbounded. Add explicit cleanup cron or external object storage (S3) for the `/app/processed` directory when running multiple containers.

## Anti-Patterns

### Anti-Pattern 1: Downloading Models at Container Start

**What people do:** Write a shell script or Python startup code that downloads model files on first run if they're missing.
**Why it's wrong:** Creates containers that fail without internet access, inconsistent behavior between runs (first run slow, subsequent fast), breaks air-gapped deployments, no checksum verification. The entire value of bundling is lost.
**Do this instead:** Download all models in the `model-downloader` Dockerfile stage. The image is larger but fully self-contained. Verify with `COPY --from=model-downloader` — if the download failed during build, the build fails, not the container.

### Anti-Pattern 2: Using CUDA devel Image for Production

**What people do:** Use `nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04` as the production base because it's what they used for building.
**Why it's wrong:** The devel image includes CUDA headers, nvcc compiler, and development libraries — adds ~3-5GB that is unnecessary at inference time. devel images are for compiling CUDA code; runtime images are for running it.
**Do this instead:** Build in the devel image (builder stage), copy wheels to the `runtime` image: `nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04`. This is the split between Dockerfile.gpu stages 2 and 3.

### Anti-Pattern 3: Single Monolithic Dockerfile Stage

**What people do:** Write one FROM and install everything sequentially — system packages, build tools, pip install, model download, copy source.
**Why it's wrong:** Every code change invalidates the entire cache layer chain, forcing re-download of 615MB of models and re-compilation of C extensions. Build times become 20+ minutes for every change.
**Do this instead:** Separate into three stages (model-downloader → builder → production) with independent cache layers. Code changes hit only the COPY src/ layer and later. Model downloads and compilation are cached separately.

### Anti-Pattern 4: Running as Root in Production

**What people do:** Leave the container running as root (the default in most base images) for simplicity.
**Why it's wrong:** If the container process is compromised, the attacker has root access. Also breaks on Kubernetes clusters with pod security policies that reject root containers.
**Do this instead:** Create `appuser` with `useradd -m -u 1000 appuser`, set ownership of `/app` and `/home/appuser/.u2net`, switch with `USER appuser` before CMD. This is already implemented in both existing Dockerfiles.

### Anti-Pattern 5: docker-compose with Separate Files per Variant

**What people do:** Create `docker-compose.cpu.yml` and `docker-compose.gpu.yml` as separate files.
**Why it's wrong:** Configuration drift — CPU and GPU versions diverge in port mappings, env vars, volume mounts. Users must know which file to use. Docs reference two different commands.
**Do this instead:** Single `docker-compose.yml` with Docker Compose profiles. `docker compose --profile cpu up` or `docker compose --profile gpu up`. One file, one truth.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| dlib.net model host | wget at build time in model-downloader stage | File: shape_predictor_68_face_landmarks.dat.bz2. No auth required. Verify with sha256sum after decompression |
| GitHub Releases (CodeFormer) | wget at build time in model-downloader stage | URL: github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth. Stable versioned URL |
| PyPI (rembg) | pip install in model-downloader stage, triggers u2net download | rembg downloads u2net_human_seg to ~/.u2net on first new_session() call |
| Docker Hub (djok/facecraft) | docker push after successful build | Two tags: :cpu and :gpu. Build locally, push manually (no CI/CD in scope) |
| NVIDIA Container Toolkit | Host-level requirement for GPU image | Must be installed on host OS. Not in Dockerfile. Users documented in README |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| model-downloader → production | COPY --from=model-downloader | One-way artifact transfer at build time. No runtime coupling |
| builder → production | COPY --from=builder /wheels | One-way artifact transfer at build time. Wheels deleted after install in production |
| docker-compose → container | Environment variables, port binding, volume mounts | FACECRAFT_* env vars configure runtime behavior without image rebuild |
| container → host GPU | NVIDIA Container Toolkit runtime injection | Handled by Docker engine with deploy.resources.reservations.devices in compose |
| rembg ← u2net model | /home/appuser/.u2net/ directory | rembg hardcodes this path based on home directory. Cannot be redirected via FACECRAFT_MODELS_DIR |

## Build Order Implications

The three-stage structure has a specific ordering constraint that affects roadmap task sequencing:

1. **model-downloader stage must be authored and verified first.** All three model downloads must succeed for any image to be buildable. If model URLs are wrong or sources are unavailable, the build fails at stage 1.

2. **builder stage depends on requirements.txt accuracy.** The CPU builder uses `requirements.txt`; the GPU builder uses both `requirements.txt` and `requirements-gpu.txt`. These files must correctly specify all dependencies before the builder stage can produce valid wheels.

3. **production stage is last and integrates everything.** It cannot be tested until model-downloader and builder both succeed. However, it is the only stage that changes on code edits — stages 1 and 2 are cache-stable.

4. **docker-compose.yml is independent of build.** It references pre-built images by tag (`djok/facecraft:cpu`). The compose file can be authored and validated before images are pushed; validation requires the images to be pulled or built locally.

5. **README.md is last.** Accurate commands and environment variable documentation depend on the final compose file and image tags being stable.

## Sources

- Docker multi-stage builds official docs: https://docs.docker.com/build/building/multi-stage/ (HIGH confidence)
- Docker Compose GPU support official docs: https://docs.docker.com/compose/how-tos/gpu-support/ (HIGH confidence)
- Docker Dockerfile ADD --checksum and RUN --mount=type=cache: https://docs.docker.com/reference/dockerfile/ (HIGH confidence)
- Existing Dockerfile.cpu and Dockerfile.gpu in /home/rosen/facecraft/docker/ (HIGH confidence — ground truth)
- Collabnix AI containers multi-stage builds guide: https://collabnix.com/optimize-your-ai-containers-with-docker-multi-stage-builds-a-complete-guide/ (MEDIUM confidence)
- Downloading model verification patterns: https://www.coguard.io/post/how-to-verify-your-downloads-in-docker-builds (MEDIUM confidence)
- Docker Compose profiles official docs: https://docs.docker.com/compose/how-tos/profiles/ (HIGH confidence)

---
*Architecture research for: Docker packaging of Facecraft ML API (CPU + GPU)*
*Researched: 2026-02-18*
