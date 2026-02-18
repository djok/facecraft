# Facecraft — Professional Docker Release

## What This Is

Facecraft is an AI-powered portrait photo processing API (FastAPI) that handles face detection, background removal, face enhancement (CodeFormer), and professional photo output. Published to Docker Hub as `djok/facecraft:cpu` and `djok/facecraft:gpu` — self-contained images with all models bundled, zero configuration required.

## Core Value

A user pulls the Docker image and runs it — everything works immediately with zero configuration, zero internet downloads, zero manual model setup.

## Requirements

### Validated

- ✓ FastAPI REST API with process/quick/batch endpoints — existing
- ✓ Face detection via dlib — existing
- ✓ Background removal via rembg (u2net_human_seg) — existing
- ✓ Face enhancement via CodeFormer — existing
- ✓ Photo enhancement (exposure, white balance, sharpening) — existing
- ✓ CPU and GPU Dockerfiles — existing
- ✓ Health/readiness endpoints — existing
- ✓ Environment-based configuration — existing
- ✓ Docker images fully self-contained (all models bundled, no runtime downloads) — v1.0
- ✓ CPU image published to `djok/facecraft:cpu` — v1.0
- ✓ GPU image published to `djok/facecraft:gpu` — v1.0
- ✓ `docker run` one-liner works out of the box with zero config — v1.0
- ✓ `docker-compose.yml` with CPU + GPU profiles for production deployment — v1.0
- ✓ README.md rewritten in English with Hub-first quickstart, API reference, configuration guide — v1.0
- ✓ Dockerfiles optimized with multi-stage builds and SHA256 model verification — v1.0
- ✓ `.dockerignore` properly configured — v1.0
- ✓ HEALTHCHECK instruction targeting `/ready` with 180s start-period — v1.0
- ✓ All models verified to load correctly inside container at build time — v1.0

### Active

(None — next milestone requirements TBD)

### Out of Scope

- CI/CD pipeline (GitHub Actions for automated Docker Hub push on tag)
- ARM64 / Apple Silicon image support
- Kubernetes manifests / Helm chart
- Image size reduction below current levels
- Code refactoring (logging, async improvements)
- New API features or endpoints
- Semantic version tags (`:1.0.0-cpu`, `:1.0.0-gpu`)

## Context

Shipped v1.0 with 2,005 LOC Python. 3 phases, 7 plans executed in 18 days.

- CPU image: 4.08 GB uncompressed, 8.7 GB compressed on Hub
- GPU image: 13.8 GB uncompressed, ~8.7 GB compressed on Hub
- Models bundled: dlib shape predictor (95 MB), CodeFormer (350 MB), u2net (170 MB)
- Tech stack: FastAPI, PyTorch 2.0.1, dlib, rembg, CodeFormer, Docker, Docker Compose
- Docker Hub: `djok/facecraft` with `:cpu` and `:gpu` tags (no `:latest`)
- Smoke test verified: `/health` 200, end-to-end image processing returns valid PNG

Known deferred item: Docker Hub description sync (PUBL-03) — can be done manually.

## Constraints

- **Registry**: Docker Hub (`docker.io/djok/facecraft`)
- **Tags**: `:cpu` and `:gpu` only (never `:latest`)
- **Models**: Downloaded and verified at build time with SHA256 checksums
- **Documentation**: English only
- **Base images**: `python:3.11-slim` (CPU), `nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04` (GPU)
- **PyTorch**: Pinned at `torch==2.0.1` + `torchvision==0.15.2` (basicsr 1.4.2 compatibility)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Bundle all models in Docker image | Zero-config user experience, no internet needed at runtime | ✓ Good — air-gap verified |
| CPU + GPU as separate images | Different base images and dependencies, keeps CPU image smaller | ✓ Good — CPU 4.08 GB vs GPU 13.8 GB |
| docker-compose.yml with both variants | Users pick CPU or GPU profile, single config file | ✓ Good — validated |
| English-only documentation | International audience, standard for open source | ✓ Good |
| PyTorch pinned at 2.0.1 | basicsr 1.4.2 breaks on torchvision 0.16+ | ✓ Good — avoids dependency hell |
| CUDA 12.1.0 base image | PyTorch 2.0.1 only has cu118 wheels, upgrading provides no benefit | ✓ Good |
| No `:latest` tag | Avoids ambiguity between CPU and GPU variants | ✓ Good — users must choose explicitly |
| Compose profiles (no always-on service) | Prevents port 8000 conflicts between CPU and GPU | ✓ Good |
| Hub-first README structure | Pull/run command in first 10 lines, build instructions at bottom | ✓ Good — 9.2 KB, Hub-compatible |

---
*Last updated: 2026-02-18 after v1.0 milestone*
