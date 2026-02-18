# Facecraft — Professional Docker Release

## What This Is

Facecraft is an AI-powered portrait photo processing API (FastAPI) that handles face detection, background removal, face enhancement (CodeFormer), and professional photo output. This milestone focuses on making it production-ready with professional Docker packaging — self-contained images (CPU + GPU) published to Docker Hub (`djok/facecraft`), with clear English documentation so anyone can run it with a single command.

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

### Active

- [ ] Docker images are fully self-contained (all models bundled, no runtime downloads)
- [ ] CPU image published to `djok/facecraft:cpu`
- [ ] GPU image published to `djok/facecraft:gpu`
- [ ] `docker run` one-liner works out of the box with zero config
- [ ] `docker-compose.yml` provided for production deployment (CPU + GPU variants)
- [ ] README.md rewritten in English with clear quickstart, API reference, configuration guide
- [ ] Dockerfiles optimized (multi-stage builds, layer caching, minimal image size)
- [ ] `.dockerignore` properly configured to exclude unnecessary files
- [ ] Health check configured in Docker (HEALTHCHECK instruction)
- [ ] All models verified to load correctly inside container at build time

### Out of Scope

- New API features or endpoints — this milestone is packaging only
- Code refactoring (logging, error handling, async) — separate milestone
- CI/CD pipeline — can be added later
- Kubernetes manifests — Docker Compose is sufficient for now
- Test suite improvements — separate milestone

## Context

- Existing codebase is functional but Docker images may download models at runtime
- Models total ~615MB (dlib shape predictor 95MB, CodeFormer 350MB, u2net ~170MB)
- CPU image currently ~16.6GB, GPU image ~23.5GB — optimization desirable
- Docker Hub repo: `djok/facecraft` (already exists, needs new version)
- Tags: `cpu` and `gpu` (latest)
- Target audience: developers who want to self-host portrait processing

## Constraints

- **Registry**: Docker Hub (`docker.io/djok/facecraft`)
- **Tags**: `:cpu` and `:gpu`
- **Models**: Must be downloaded and verified at build time, not runtime
- **Documentation**: English only
- **Base images**: `python:3.11-slim` (CPU), `nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04` (GPU)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Bundle all models in Docker image | Zero-config user experience, no internet needed at runtime | — Pending |
| CPU + GPU as separate images | Different base images and dependencies, keeps CPU image smaller | — Pending |
| docker-compose.yml with both variants | Users pick CPU or GPU profile, single config file | — Pending |
| English-only documentation | International audience, standard for open source | — Pending |

---
*Last updated: 2026-02-18 after initialization*
