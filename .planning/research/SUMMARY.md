# Project Research Summary

**Project:** Facecraft Docker Hub Publishing Milestone
**Domain:** Docker packaging of ML inference API — bundled models, CPU/GPU image variants, Docker Hub distribution
**Researched:** 2026-02-18
**Confidence:** HIGH

## Executive Summary

Facecraft is a working FastAPI inference API built on PyTorch, dlib, CodeFormer, and rembg that needs to be packaged and published to Docker Hub as two production-quality images: `:cpu` and `:gpu`. The foundational architecture is already correct — both Dockerfiles implement a sound three-stage pattern (model-downloader, builder, production) with non-root user and HEALTHCHECK. The milestone is not a redesign: it is a targeted hardening, optimization, and publishing exercise with a documentation rewrite to produce a professional Docker Hub presence.

The recommended approach is to address five concrete gaps in the existing Dockerfiles (CPU PyTorch wheel source, model integrity checksums, OCI labels, `.dockerignore`, and HEALTHCHECK timing), add a `docker-compose.yml` with CPU and GPU profiles, rewrite README for Hub-first consumption, and publish manually using `docker build && docker push`. The images are then self-contained and zero-config: all three ML models (~615MB total) are bundled at build time, which is Facecraft's strongest differentiator against comparable Hub images (Whisper ASR, faster-whisper) where models download at first run.

The primary risks are technical debt in the existing Dockerfiles: the CPU image likely installs 2.5GB of unnecessary CUDA PyTorch wheels, model downloads have no integrity verification, and the HEALTHCHECK may fire before models finish loading. Each of these has a clear, low-effort fix. The dependency landscape is fragile — `basicsr==1.4.2` imports a removed `torchvision.transforms.functional_tensor` API, so PyTorch must stay pinned at 2.0.1 + torchvision 0.15.2 until basicsr is patched. Deviating from this pin will break CodeFormer silently at runtime.

---

## Key Findings

### Recommended Stack

The existing stack is functionally correct and should not be changed at the library level. The work is at the Docker packaging layer. BuildKit (builtin since Docker 23+) should be used explicitly with `DOCKER_BUILDKIT=1`. The CPU runtime base (`python:3.11-slim` on Debian Bookworm) is the correct choice — Alpine must never be used because dlib, OpenCV, and PyTorch require glibc. The GPU runtime base should be upgraded from the current `nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04` to `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04`, which has broader PyTorch wheel support and a longer support horizon.

Publishing to Docker Hub should use `docker/build-push-action@v6` in GitHub Actions when CI/CD is added, but for this milestone manual `docker push` is sufficient. The `docker/metadata-action@v5` generates correct OCI labels and Docker Hub metadata automatically from git tags — useful when CI is added. `docker buildx bake` with a `docker-bake.hcl` file allows both CPU and GPU images to be built in parallel with one command, which is worth adding even before CI/CD.

**Core technologies:**
- `python:3.11-slim` (CPU base): Minimal glibc Python image, dlib/OpenCV/PyTorch compatible — never use Alpine
- `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04` (GPU runtime base): Upgrade from 12.1; runtime not devel keeps final image lean
- `torch==2.0.1 + torchvision==0.15.2`: Pinned hard — basicsr breaks on torchvision 0.16+; do not upgrade without patching basicsr
- `--extra-index-url https://download.pytorch.org/whl/cpu`: Required for CPU image to get CPU-only wheels (~600MB vs ~2.5GB CUDA wheels)
- `docker/build-push-action@v6` + `docker/metadata-action@v5`: Standard CI publishing actions (future phase)
- BuildKit cache mounts: Speed up local development builds; use `--no-cache-dir` in CI
- `sha256sum` / `ADD --checksum`: Model integrity verification at build time — currently missing

### Expected Features

All research agrees on a clear MVP boundary. The images and documentation are inseparable: publishing images without Hub-first documentation produces a professional image that looks abandoned.

**Must have (table stakes):**
- `djok/facecraft:cpu` and `djok/facecraft:gpu` published to Docker Hub — the product doesn't exist without this
- Working `docker run -p 8000:8000 djok/facecraft:cpu` one-liner — first thing developers try
- `docker-compose.yml` with CPU and GPU profiles in one file — GPU `deploy.resources.reservations.devices` syntax is a known pain point; correct example is a differentiator
- README rewritten for Hub-first consumption: one-liner, env var table, model inventory, performance benchmarks, image sizes, volume mount example
- OCI standard labels (`org.opencontainers.image.*`) in both Dockerfiles — signals professionalism to tooling
- HEALTHCHECK validated with adequate `--start-period` (minimum 120s, 180s safer) — prevents false-healthy containers

**Should have (competitive):**
- Performance benchmarks prominently in README (1.45s CPU, 0.43s GPU already measured) — rare among comparable Hub images; lets users choose variant before pulling
- Image size transparency (current: 16.6GB CPU / 23.5GB GPU; optimized: ~8GB CPU / ~12GB GPU target) — hiding size erodes trust
- Bundled models as lead differentiator in README — most comparable images download at runtime; zero-config startup is Facecraft's strongest UX claim
- Semantic version tags (`:1.0.0-cpu`, `:1.0.0-gpu`) alongside `:cpu`/`:gpu` — added with first update

**Defer (v2+):**
- ARM64/Apple Silicon support — dlib arm64 compilation is non-trivial; separate milestone
- GitHub Actions CI/CD for automated Hub publishing — explicitly out of scope for this milestone
- Image size reduction below current targets — accept current size; optimize if users report pull friction
- Kubernetes manifests/Helm chart — compose is sufficient; k8s users customize anyway

### Architecture Approach

The three-stage multi-stage build is already implemented and correct: `model-downloader` (downloads all three ML models at build time into `/models/`), `builder` (compiles dlib C extensions and pre-builds Python wheels into `/wheels/`), and `production` (minimal runtime image that copies from both prior stages). The key architectural constraint is build-order dependency: model-downloader must succeed before builder can complete, and both must succeed before the production stage can be tested. Code changes only invalidate the production stage, making development rebuilds fast after first build.

The runtime orchestration layer consists of a single `docker-compose.yml` with Compose profiles — one file, two services (`facecraft-cpu` and `facecraft-gpu`) activated via `--profile cpu` or `--profile gpu`. This avoids configuration drift from separate compose files. README is the final artifact and depends on stable compose commands and Hub tags — it should be written last.

**Major components:**
1. `docker/Dockerfile.cpu` — 3-stage CPU build: python:3.11-slim throughout; CPU-only PyTorch wheels
2. `docker/Dockerfile.gpu` — 3-stage GPU build: cuda:devel for builder, cuda:runtime for production
3. `docker-compose.yml` — single file with cpu and gpu profiles; correct GPU device reservation syntax
4. `.dockerignore` — prevents `__pycache__`, `.git`, `.env`, `tests/`, model caches from bloating build context
5. `README.md` — Hub-first documentation: one-liner, benchmarks, model table, env var reference

### Critical Pitfalls

1. **CPU image installs CUDA PyTorch wheels (~2.5GB bloat)** — fix by adding `--extra-index-url https://download.pytorch.org/whl/cpu` to the builder pip wheel step and pinning `torch==2.0.1+cpu` in requirements.txt; verify with `docker run djok/facecraft:cpu python -c "import torch; print(torch.version.cuda)"` — must print `None`

2. **Model downloads have no integrity verification** — if `wget` fails silently or dlib.net is unavailable, the build may complete with corrupt/missing models that only fail at runtime; add `sha256sum -c` after each download, or use `ADD --checksum=sha256:<hash>` (BuildKit-native); test with `docker run --network none djok/facecraft:cpu` — container must start without internet

3. **HEALTHCHECK may false-kill container during slow model load** — if models are lazy-loaded on first request (not at FastAPI lifespan startup), the app responds to `/health` immediately but isn't ready; HEALTHCHECK should target a `/readiness` endpoint that returns 503 until models are loaded, not `/health`; `--start-period` should be 180s minimum

4. **PyTorch version pin must not be relaxed** — `basicsr==1.4.2` imports `torchvision.transforms.functional_tensor` which was removed in torchvision 0.16+ (PyTorch 2.1+); upgrading without patching basicsr produces a silent import failure in CodeFormer at runtime; stay at `torch==2.0.1` + `torchvision==0.15.2`

5. **No `:latest` tag — ever** — `djok/facecraft:latest` creates ambiguity between CPU and GPU; users pull the wrong 16-23GB image; README and Docker Hub short description must show only `:cpu` and `:gpu` explicitly; no `:latest` tag should be pushed

6. **rembg u2net model path ownership** — model is at `/home/appuser/.u2net/` which must be `chown -R appuser:appuser` after COPY; if ownership order is wrong during Dockerfile refactoring, runtime ONNX errors appear (not startup errors)

---

## Implications for Roadmap

The research reveals a clear sequential dependency chain: Dockerfiles must be correct before images can be built, images must be built and pushed before compose can be tested against Hub images, and README must be written after compose commands are finalized. This maps naturally to four phases.

### Phase 1: Dockerfile Hardening
**Rationale:** Everything downstream depends on correct, optimized Dockerfiles. The existing Dockerfiles are structurally sound but have five concrete gaps. This phase has no dependencies; it can be started immediately.
**Delivers:** Both Dockerfiles are correct, optimized, and production-ready — ready to build publishable images
**Addresses:** CPU-only PyTorch wheels, model SHA256 verification, OCI labels, `.dockerignore`, CUDA base image upgrade to 12.4
**Avoids:** CPU image CUDA bloat (Pitfall 1), silent model corruption (Pitfall 3), CUDA devel base in production (Pitfall 2)
**Tasks:**
- Add `--extra-index-url https://download.pytorch.org/whl/cpu` to Dockerfile.cpu builder stage
- Add SHA256/md5 checksum verification after each model download
- Add OCI standard labels to both Dockerfiles
- Add `.dockerignore`
- Upgrade GPU base to `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04`
- Verify HEALTHCHECK start-period (set to 180s)

### Phase 2: Image Build and Verification
**Rationale:** Can only run after Dockerfiles are hardened. Building both images provides the artifacts needed for Phase 3 (compose) and allows the verification checklist from PITFALLS.md to be executed. This is the longest clock-time phase due to build time (model downloads, dlib compilation).
**Delivers:** Verified `djok/facecraft:cpu` and `djok/facecraft:gpu` images ready to push
**Uses:** Both Dockerfiles, BuildKit, dive for layer inspection
**Implements:** model-downloader → builder → production pipeline
**Avoids:** Lazy model load (Pitfall 4), non-root user permission error (Pitfall 5), `:latest` tag ambiguity (Pitfall 6)
**Verification checklist (from PITFALLS.md):**
- `docker run --network none djok/facecraft:cpu` — starts without internet
- `docker run djok/facecraft:cpu python -c "import torch; print(torch.version.cuda)"` — prints `None`
- `docker run --gpus all djok/facecraft:gpu python -c "import torch; print(torch.cuda.is_available())"` — prints `True`
- `docker run --rm djok/facecraft:cpu whoami` — prints `appuser`
- `docker images djok/facecraft` — CPU <8GB, GPU <12GB after optimization

### Phase 3: Docker Compose and Orchestration
**Rationale:** Compose file targets Hub images (`djok/facecraft:cpu`, `djok/facecraft:gpu`) — it cannot be fully validated until those images exist (locally or on Hub). Compose profiles are the correct single-file pattern; incorrect GPU `deploy.resources` syntax is the most common user pain point in comparable images.
**Delivers:** `docker-compose.yml` with working CPU and GPU profiles; tested GPU device reservation syntax
**Implements:** docker-compose profiles pattern (Pattern 3 from ARCHITECTURE.md)
**Avoids:** GPU compose syntax errors (documented as most common user pain point in FEATURES.md competitor analysis)
**Tasks:**
- Write `docker-compose.yml` with `profiles: [cpu]` and `profiles: [gpu]`
- Include `deploy.resources.reservations.devices` with `capabilities: [gpu]`
- Include volume mount examples for `/app/uploads` and `/app/processed`
- Include inline comments for all configurable ENV vars
- Test `docker compose --profile cpu up` end-to-end

### Phase 4: Docker Hub Publish and Documentation
**Rationale:** README must be written after compose commands and Hub tags are stable — commands in the README must be copy-paste testable. Publishing and documentation are combined because Docker Hub long description and README.md must be in sync.
**Delivers:** Images live on Docker Hub; README complete with Hub-first quickstart, benchmarks, model table
**Addresses:** All FEATURES.md P1 items: working one-liner, env var reference, model inventory, performance benchmarks, image size transparency, bundled-models differentiator
**Avoids:** `:latest` tag ambiguity, README/Hub description drift, docker run without port mapping (UX pitfall)
**Tasks:**
- Push `:cpu` and `:gpu` tags (no `:latest`)
- Rewrite README: Hub one-liner first, performance table, model inventory table, env var reference, image size transparency, volume mount example
- Update Docker Hub short description: "Use :cpu or :gpu tags — no :latest tag"
- Add Swagger UI URL to README (`/docs`)
- Verify Hub long description matches README.md after publish

### Phase Ordering Rationale

- Phase 1 before Phase 2: Dockerfiles must be correct before images are worth building
- Phase 2 before Phase 3: Compose targets Hub images; full validation requires them to exist
- Phase 3 before Phase 4: README commands reference compose commands; compose must be finalized first
- Phase 4 is last: Documentation accuracy depends on stable image tags and working compose — write it last, not first

The architecture's build-order constraint (model-downloader → builder → production) maps directly to why Phase 2 is its own phase: the full build pipeline must be executed and verified before moving to orchestration and publishing. Code changes in Phase 3 or 4 only invalidate the fast production stage, not the slow model/compilation stages.

### Research Flags

Phases with standard, well-documented patterns (skip `/gsd:research-phase`):
- **Phase 1 (Dockerfile Hardening):** All changes are prescriptive — exact Dockerfile syntax in STACK.md and PITFALLS.md; no ambiguity
- **Phase 2 (Image Build/Verification):** Standard `docker build` workflow; verification commands fully specified in PITFALLS.md checklist
- **Phase 3 (Docker Compose):** Official Docker Compose GPU docs are authoritative; compose syntax is in ARCHITECTURE.md Pattern 3
- **Phase 4 (Publish/Documentation):** Manual push workflow; README content is fully specified in FEATURES.md

No phases require deeper research during planning. All decisions are resolved in the research files. The one technical uncertainty — whether `basicsr` will be updated to fix the torchvision import — does not affect this milestone (we stay pinned regardless).

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core Docker best practices verified against official docs; PyTorch version pin confirmed via multiple GitHub issues; CUDA compatibility verified via NGC catalog |
| Features | MEDIUM | Docker Hub ML image conventions are community-standard, not formally specified; competitor analysis validates approach but is observational |
| Architecture | HIGH | Existing Dockerfiles inspected directly; patterns verified against official Docker docs; data flow traced through actual codebase |
| Pitfalls | HIGH | Multiple authoritative sources per pitfall; several confirmed via actual GitHub issues (e.g., pytorch/pytorch#146786, BasicSR#711); internal CONCERNS.md audit corroborates |

**Overall confidence:** HIGH

### Gaps to Address

- **Actual model SHA256 hashes are not known:** The research identifies the need for checksum verification but does not provide the actual hashes for the three model files. During Phase 1, compute hashes from the live model downloads (`sha256sum shape_predictor_68_face_landmarks.dat`, etc.) and embed them in the Dockerfile. This is a one-time cost.

- **rembg u2net_human_seg model download behavior is implementation-dependent:** The model-downloader stage triggers `new_session()` to pre-cache u2net. If rembg's API or cache path changes in a future version, the build behavior changes. Verified against current rembg docs; lock the rembg version in requirements.txt.

- **Actual post-optimization image sizes are not measured:** The pitfalls research predicts <8GB CPU and <12GB GPU after optimization. These are targets, not guarantees. Phase 2 must measure actual sizes and adjust if needed.

- **HEALTHCHECK start-period adequacy is environment-dependent:** 180s is a conservative buffer. The actual model load time on typical cloud VMs should be measured during Phase 2 testing. If load takes >120s consistently, consider adding explicit model pre-loading in the FastAPI lifespan startup event.

---

## Sources

### Primary (HIGH confidence)
- Docker Multi-stage Builds — https://docs.docker.com/build/building/multi-stage/
- Docker Build Best Practices — https://docs.docker.com/build/building/best-practices/
- Docker Compose GPU support — https://docs.docker.com/compose/how-tos/gpu-support/
- Docker Compose profiles — https://docs.docker.com/compose/how-tos/profiles/
- Dockerfile ADD --checksum reference — https://docs.docker.com/reference/dockerfile/#add
- GitHub Actions Docker Build+Push Action v6 — https://github.com/docker/build-push-action
- OCI image annotation spec — https://github.com/opencontainers/image-spec/blob/main/annotations.md
- basicsr torchvision.functional_tensor breakage — https://github.com/XPixelGroup/BasicSR/issues/711
- PyTorch CUDA in CPU image — https://github.com/pytorch/pytorch/issues/146786
- Existing Dockerfile.cpu and Dockerfile.gpu — /home/rosen/facecraft/docker/ (ground truth)
- Existing codebase concerns — /home/rosen/facecraft/.planning/codebase/CONCERNS.md

### Secondary (MEDIUM confidence)
- PyTorch Docker 60% size reduction — https://mveg.es/posts/optimizing-pytorch-docker-images-cut-size-by-60percent/
- linuxserver/faster-whisper documentation — https://docs.linuxserver.io/images/docker-faster-whisper/
- Whisper ASR Webservice usage — https://ahmetoner.com/whisper-asr-webservice/run/
- NVIDIA CUDA devel vs runtime vs base — https://forums.developer.nvidia.com/t/whats-the-difference-between-runtime-and-devel-docker/180288
- rembg official repo (model path) — https://github.com/danielgatis/rembg
- PyTorch CPU-only Docker optimization (Feb 2025) — https://shekhargulati.com/2025/02/05/reducing-size-of-docling-pytorch-docker-image/

### Tertiary (LOW confidence)
- DataCamp Docker ML images overview — https://www.datacamp.com/blog/docker-container-images-for-machine-learning-and-ai (editorial)

---

*Research completed: 2026-02-18*
*Ready for roadmap: yes*
