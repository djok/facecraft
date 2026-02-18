---
status: passed
phase: 01-dockerfile-hardening
verified: 2026-02-18
score: 5/5
---

# Phase 1: Dockerfile Hardening - Verification

## Phase Goal
Both Dockerfiles are correct, optimized, and ready to produce publishable images -- no bloat, no missing integrity checks, no missing metadata

## Success Criteria Verification

### 1. CPU-only PyTorch wheels
**Status:** PASSED
**Evidence:** `docker/Dockerfile.cpu` line 60 contains `--extra-index-url https://download.pytorch.org/whl/cpu`
**Note:** Full verification requires building the image and running `python -c "import torch; print(torch.version.cuda)"` -- expected output: `None`. This is a build-time verification that can be confirmed in Phase 2.

### 2. SHA256 checksum verification for all model downloads
**Status:** PASSED
**Evidence:**
- `docker/Dockerfile.cpu`: 3 instances of `sha256sum -c --quiet` (lines 28, 33, 38)
- `docker/Dockerfile.gpu`: 3 instances of `sha256sum -c --quiet` (lines 28, 33, 38)
- Real SHA256 hashes computed from live model downloads and embedded as ARG values
- Build will fail on checksum mismatch (sha256sum exits non-zero)

### 3. OCI standard labels
**Status:** PASSED
**Evidence:**
- `docker/Dockerfile.cpu` line 68: `org.opencontainers.image.source`, `.version`, `.description`, `.licenses` present
- `docker/Dockerfile.gpu` line 80: Same labels present with GPU/CUDA variant description
- No legacy `LABEL maintainer=` found in either file (0 occurrences)

### 4. .dockerignore configuration
**Status:** PASSED
**Evidence:** `.dockerignore` line 6 contains `.planning`
**Pre-existing exclusions verified:** `.git` (line 2), `tests` (line 34), `__pycache__` (line 7), `.env` (line 55)

### 5. HEALTHCHECK targeting /ready with 180s start-period
**Status:** PASSED
**Evidence:**
- `docker/Dockerfile.cpu` line 123: `--start-period=180s`, line 124: `/ready`
- `docker/Dockerfile.gpu` line 140: `--start-period=180s`, line 141: `/ready`

## Additional Verification

### Makefile update-checksums target
**Status:** PASSED
**Evidence:** `Makefile` exists at repo root with `.PHONY: update-checksums` target. Dry run (`make -n update-checksums`) succeeds. Target patches both Dockerfiles via sed.

### CUDA base image unchanged
**Status:** PASSED
**Evidence:** `docker/Dockerfile.gpu` still uses `nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04` (builder) and `nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04` (runtime). Decision documented in STATE.md.

## Human Verification Items

None required for this phase. All criteria are statically verifiable from file contents. Full runtime verification (torch.version.cuda == None, build succeeds with checksums) will occur in Phase 2 when images are built.

## Score

5/5 success criteria verified. Phase goal achieved.
