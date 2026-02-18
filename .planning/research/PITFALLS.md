# Pitfalls Research

**Domain:** Docker packaging of ML/AI APIs — bundled models, Docker Hub publishing, CPU/GPU image variants
**Researched:** 2026-02-18
**Confidence:** HIGH (multiple authoritative sources, verified against official docs and community post-mortems)

---

## Critical Pitfalls

### Pitfall 1: CPU Image Pulls Full CUDA PyTorch Wheels

**What goes wrong:**
The CPU Dockerfile installs PyTorch using a plain `pip install torch==2.0.1`, which pulls CUDA-bundled wheels (~2.5GB) even though no GPU is present. This adds ~2.5GB of dead weight to the CPU image. The current 16.6GB CPU image almost certainly contains this bloat.

**Why it happens:**
PyTorch's default PyPI distribution bundles CUDA binaries. As of PyTorch 2.5.1, even when using `python:3.11-slim` as base (no GPU), `pip install torch` without specifying `--extra-index-url https://download.pytorch.org/whl/cpu` fetches the CUDA-enabled variant. A GitHub issue filed February 2025 confirms this is still an active problem.

**How to avoid:**
In `Dockerfile.cpu`, change the wheel-build step:
```dockerfile
RUN pip wheel --no-cache-dir --wheel-dir /wheels \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt
```
And ensure `requirements.txt` pins `torch==2.0.1+cpu` explicitly, not just `torch==2.0.1`.

**Warning signs:**
- CPU image >10GB is a strong indicator
- Run `docker history djok/facecraft:cpu` — if you see a 2.5GB layer mentioning torch, this pitfall is active
- `pip show torch` inside a running container shows CUDA wheels installed

**Phase to address:** Dockerfile optimization phase (first build task)

---

### Pitfall 2: GPU Image Uses `devel` Base Instead of `runtime`

**What goes wrong:**
`nvidia/cuda:12.1.0-cudnn8-devel` adds ~4-5GB of CUDA compiler toolchain (headers, nvcc, debuggers, profilers) that are only needed to compile CUDA kernels — not to run PyTorch inference. The current GPU image uses `runtime` for the production stage correctly, but the `builder` stage uses `devel`, and if any layer from `devel` bleeds into production or is left in the final image, it inflates the image by 3-5GB.

**Why it happens:**
Developers copy the pattern for compiling CUDA code and use `devel` everywhere. PyTorch bundles its own CUDA binaries, so the runtime image needs only `nvidia/cuda:<ver>-base-ubuntu22.04` for the final stage — the base variant (800MB) vs devel (5GB). Switching to `nvidia/cuda:12.1.0-base-ubuntu22.04` for the production stage achieves a further 26% reduction beyond what the current Dockerfile does.

**How to avoid:**
- Builder stage: keep `devel` (needed for dlib compilation and wheel building)
- Production stage: switch to `nvidia/cuda:12.1.0-runtime-ubuntu22.04` or even `base` — PyTorch wheels bundle the CUDA runtime
- Verify: `docker image inspect djok/facecraft:gpu --format '{{.Size}}'` should be <8GB after fix

**Warning signs:**
- GPU image >20GB is a strong indicator
- `docker history` shows `/usr/local/cuda` layer >4GB in the production stage

**Phase to address:** Dockerfile optimization phase

---

### Pitfall 3: Model Download at Build Time Fails Silently, Falls Back to Runtime

**What goes wrong:**
If the `wget` download in the model-downloader stage fails (network timeout, GitHub release URL changes, dlib.net goes down), the build may succeed with a 0-byte or missing model file. The application then downloads the model at container startup, which breaks the zero-config guarantee and causes 60–120 second cold starts in production.

**Why it happens:**
`wget -q` suppresses output including errors. Docker's RUN layer succeeds based on exit code, but if a partial file exists, bunzip2 may silently truncate or error out in a way that doesn't fail the build. The rembg stage is especially risky — `new_session()` downloads from internet even inside the build container.

**How to avoid:**
- Add checksums after each download:
```dockerfile
RUN wget -q http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2 \
    && bunzip2 shape_predictor_68_face_landmarks.dat.bz2 \
    && echo "d527a3620200929aa8ccdb06e7f3ce0a  shape_predictor_68_face_landmarks.dat" | md5sum -c -
```
- For CodeFormer: verify file size (`ls -la codeformer.pth` should be ~350MB)
- Add a build-time verification step that imports each model and checks it loads
- Mirror critical models to a stable URL (GitHub releases are persistent; dlib.net is not)

**Warning signs:**
- Container starts up and logs show "Downloading model..." — this should never appear
- First request takes >60 seconds
- `/health` returns 200 but `/readiness` (or first actual request) fails

**Phase to address:** Model bundling verification phase

---

### Pitfall 4: Health Check Kills Container During Slow Model Load

**What goes wrong:**
The current HEALTHCHECK has `--start-period=120s`. PyTorch model loading (CodeFormer ~350MB + dlib + rembg ONNX) can take 30–90 seconds on first access, especially when lazy-loaded on first request rather than at startup. If the health check fires before models are loaded and the app isn't serving, Docker marks the container unhealthy and orchestrators (Docker Compose healthcheck-dependent services, Kubernetes) refuse to route traffic or restart the container in a crash loop.

**Why it happens:**
Lazy initialization (models loaded on first request, not at startup) means the app responds to `/health` immediately but isn't actually ready to process images. The existing codebase has exactly this pattern — `CONCERNS.md` confirms "Models loaded synchronously on every request" as a known performance bottleneck.

**How to avoid:**
- Implement a separate `/readiness` endpoint that returns 503 until models are loaded
- Pre-load all models in the FastAPI `lifespan` startup event, not on first request
- Use `--start-period=180s` as a safety buffer during optimization
- HEALTHCHECK should hit `/readiness` not `/health`:
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD curl -f http://localhost:8000/readiness || exit 1
```

**Warning signs:**
- Docker reports container status `(health: starting)` for more than 2 minutes
- Logs show "Model loaded" appearing after container is marked healthy
- Container restarts in loops without clear error

**Phase to address:** Docker health check + startup configuration phase

---

### Pitfall 5: Non-Root User Cannot Write to Model Directory at Runtime

**What goes wrong:**
The Dockerfiles correctly create a `appuser` (UID 1000) and `chown` the `/app` directory. However, rembg expects to write its model cache to `/home/appuser/.u2net`. If the `COPY --from=model-downloader` for u2net happens before the `useradd` command, or if the directory ownership is set incorrectly, the container starts as `appuser` but cannot write the ONNX model cache. The symptom is a cryptic ONNX runtime error on first image processing, not at startup.

**Why it happens:**
The current GPU Dockerfile has `useradd` after the `COPY` operations — this means `/home/appuser` is created by `useradd` but `chown` of `.u2net` is done explicitly. If this ordering is ever changed, permissions break. Also, when users mount volumes (`-v /local/models:/home/appuser/.u2net`) the host directory owner may differ from container UID 1000.

**How to avoid:**
- Explicitly `chown -R appuser:appuser /home/appuser/.u2net` after the COPY (current Dockerfiles do this — verify it survives refactoring)
- Test the exact `docker run` command with a non-root user against the final image
- Add startup validation: `assert os.access("/home/appuser/.u2net", os.R_OK)`
- Document the volume mount UID requirement for users who choose to externalize models

**Warning signs:**
- `PermissionError: [Errno 13] Permission denied: '/home/appuser/.u2net'` in container logs
- Works as `docker run --user root` but fails with default user

**Phase to address:** Image verification and testing phase

---

### Pitfall 6: `latest` Tag Ambiguity Between CPU and GPU Images

**What goes wrong:**
Publishing `djok/facecraft:latest` alongside `:cpu` and `:gpu` creates confusion. If `latest` points to GPU, users on CPU machines run `docker pull djok/facecraft` and get a 23GB CUDA image that won't start. If `latest` points to CPU, GPU users get an image without CUDA acceleration. Either way, someone is surprised and files a bug report.

**Why it happens:**
Projects with multiple image variants default to tagging one as `latest` out of convention. The Docker Hub pull page prominently shows `docker pull djok/facecraft` without a tag, defaulting to `latest`, and users follow it without reading documentation.

**How to avoid:**
- Do not push a `:latest` tag at all — force explicit tag selection
- README must show ONLY `docker pull djok/facecraft:cpu` and `docker pull djok/facecraft:gpu` — never a bare `docker pull djok/facecraft`
- Add a note in the Docker Hub short description: "Use :cpu or :gpu tags — no :latest tag"
- Consider adding `:1.0-cpu` and `:1.0-gpu` alongside `:cpu`/`:gpu` for versioned pinning

**Warning signs:**
- Docker Hub shows a `:latest` tag in the tags list
- Users report "it won't start" without specifying which tag they pulled
- Pull count for `:latest` growing without explicit intent

**Phase to address:** Docker Hub publishing + README phase

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Downloading models from dlib.net in Dockerfile | Simple, one-liner | dlib.net uptime not guaranteed; URL could change; no integrity check | Never — mirror to GitHub or use checksum verification |
| `torch==2.0.1` without CPU/GPU suffix in requirements.txt | Simpler requirements file | CPU image installs 2.5GB CUDA wheels unnecessarily | Never for CPU Dockerfile |
| Using `nvidia/cuda:*-devel` as production stage base | Compiles anything | 5GB bloat for inference-only images | Never — devel only for build stages |
| Single requirements.txt shared between CPU and GPU builds | Less maintenance | GPU image installs onnxruntime-cpu then reinstalls onnxruntime-gpu; conflicts | Acceptable if build stages properly separate wheel sets |
| `FACECRAFT_WORKERS=1` hardcoded in Dockerfile ENV | Safe default | Users cannot easily increase workers without override; misleading for GPU multi-GPU setups | Acceptable — document override pattern clearly |
| `basicsr==1.4.2` pinned hard | Reproducible | basicsr is unmaintained; Python 3.11 compatibility was experimental | Acceptable — keep pinned, add note about known breakage |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| rembg / u2net_human_seg | Placing model at `/root/.u2net` in build stage, then it's absent for `appuser` at runtime | Copy to `/home/appuser/.u2net` and `chown` explicitly before USER switch |
| Docker Hub push via GitHub Actions | Using personal password instead of Access Token; no `--no-pull` causing rate limit consumption | Use Docker Hub PAT scoped to read/write; authenticate before any `docker pull` in workflow |
| CodeFormer weights from GitHub Releases | URL `github.com/sczhou/CodeFormer/releases/download/v0.1.0/` — if repo is deleted or release removed, build breaks | Cache weights in project-controlled storage (GitHub Packages, S3, or commit hash-pinned mirror) |
| ONNX Runtime (GPU) | Installing both `onnxruntime` and `onnxruntime-gpu` in same environment — causes `ImportError: DLL load failed` | Install only `onnxruntime-gpu` for GPU images; it includes CPU fallback |
| dlib compilation in Docker | Building dlib without `libopenblas-dev` — slow fallback to pure C++, 10x slower face detection | Always include `libopenblas-dev liblapack-dev` in the builder stage |
| Docker Hub README sync | Manually updating Docker Hub long description — drifts from README.md | Automate with `peter-evans/dockerhub-description` GitHub Action on every push to main |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Lazy model initialization (load on first request) | First request takes 30–90 seconds; container reports healthy but isn't ready | Pre-load all models in FastAPI lifespan startup event | Immediately at first real user request |
| Single rembg ONNX session shared across threads | ONNX runtime crash under concurrent requests; `InvalidGraph` or race condition errors | Use a threading.Lock around rembg calls or create per-request sessions | >1 concurrent request |
| Multiple uvicorn workers each loading all models | Each worker loads PyTorch models (1.5GB+) into RAM; OOM on modest machines | Use `--workers 1` (already set) or gunicorn `--preload` to fork after model load | >2 workers on machines with <16GB RAM |
| `uploads/` and `processed/` dirs growing unbounded | Container disk fills; eventual 500 errors on new uploads | Implement cleanup (already exists) — verify 24h cleanup task runs inside container, not just in code | Hours–days of production use |
| Build cache invalidated by changing any file in `/app` | Full rebuild including model downloads on every code change (30+ min CI) | Copy only `requirements.txt` first, install deps, then copy source code last | Every code change in CI |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Docker Hub PAT stored in CI as plain secret | Token compromise allows pushing malicious images | Use GitHub Actions environment secrets with environment protection; rotate PAT every 90 days |
| `wget` without TLS verification for model downloads | MITM attack substitutes malicious model weights | Always use HTTPS URLs; add SHA256/MD5 checksum verification after each download |
| Container runs as root (USER not set) | Process escape grants host root access | Always include `USER appuser` before CMD; verify with `docker run --rm djok/facecraft:cpu whoami` |
| Image published with `FACECRAFT_API_KEY` baked into ENV | Key is visible via `docker inspect` and in Docker Hub layer history | Never bake secrets into ENV; only provide API key at `docker run -e FACECRAFT_API_KEY=...` runtime |
| Open CORS (`allow_origins=["*"]`) in production image | Any website can make API calls — browser-based data exfiltration | Set `FACECRAFT_CORS_ORIGINS` at runtime; document the default-open behavior prominently in README |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| README shows only `docker run` without port mapping | Users get "connection refused" and don't understand why | Always show full command: `docker run -p 8000:8000 djok/facecraft:cpu` |
| No example showing how to process an actual image | Users can't figure out the API without reading all docs | README must include a working `curl` command that uploads a test image |
| Pull command without tag defaults to `:latest` (which doesn't exist) | `manifest unknown` error; users think image is broken | Show `:cpu` or `:gpu` tag explicitly in every pull command |
| No indication of image size before pull | Users on slow connections start a 16GB download unexpectedly | List approximate image sizes in README (e.g., "CPU image: ~6GB after optimization") |
| Health check URL only, no readiness URL | Orchestrators route traffic before models finish loading | Add `/readiness` endpoint that returns 503 until all models are loaded |
| docker-compose.yml with no comments | Users don't know which env vars to change for their deployment | Add inline comments for every configurable ENV var in compose file |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Model bundling:** Image builds successfully but models may download at runtime — verify by running `docker run --network none djok/facecraft:cpu` and confirm startup succeeds without internet
- [ ] **CPU PyTorch:** requirements.txt says `torch==2.0.1` — verify it installed CPU-only with `docker run djok/facecraft:cpu python -c "import torch; print(torch.version.cuda)"` (should print `None`)
- [ ] **GPU acceleration:** GPU image runs but actually uses CPU — verify with `docker run --gpus all djok/facecraft:gpu python -c "import torch; print(torch.cuda.is_available())"` (should print `True`)
- [ ] **Non-root user:** Container appears to work but runs as root — verify with `docker run --rm djok/facecraft:cpu whoami` (should print `appuser`)
- [ ] **Health check timing:** HEALTHCHECK passes during CI but times out on slow machines — test with `--start-period` increased to 240s and observe behavior during model load
- [ ] **Docker Hub README:** README.md is updated in repo but Docker Hub long description still shows old content — verify Docker Hub web page after publish
- [ ] **Image size:** Optimization Dockerfile changes applied but image still large — `docker images djok/facecraft` should show <8GB CPU, <12GB GPU after optimization
- [ ] **Checksum verification:** Model download steps added checksums to Dockerfile but checksums not tested against actual files — do a clean build from scratch (`docker build --no-cache`) and verify all checks pass

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| CPU image bloated with CUDA (currently 16GB) | MEDIUM | Add `--extra-index-url https://download.pytorch.org/whl/cpu` to pip install; rebuild from scratch with `--no-cache`; expect 2-4 hour rebuild |
| Model downloads fail at runtime (not bundled) | HIGH | Identify which model isn't bundled via logs; add explicit COPY step in Dockerfile; rebuild and republish |
| Docker Hub `:latest` tag misrouting users | LOW | Delete `:latest` manifest from Docker Hub via API; update README immediately; post notice in repo issues |
| Health check killing container before model load | LOW | Increase `--start-period` in HEALTHCHECK; add model pre-loading in startup; redeploy |
| Non-root user permission denied on model dirs | MEDIUM | Add explicit `chown -R appuser:appuser` after all COPY operations; rebuild final stage only |
| Bad model weights from external URL change | HIGH | Pin model download to commit hash or content-addressed URL; add checksum verification; rebuild |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| CPU image installs CUDA PyTorch | Dockerfile optimization (CPU) | `docker run djok/facecraft:cpu python -c "import torch; print(torch.version.cuda)"` returns `None` |
| GPU devel base in production stage | Dockerfile optimization (GPU) | `docker images djok/facecraft:gpu` shows <12GB |
| Model download fails silently at build | Model bundling + checksum phase | `docker run --network none djok/facecraft:cpu` starts without error |
| Health check false-kills during model load | HEALTHCHECK configuration phase | Container reaches `healthy` status without restarting under fresh pull |
| Non-root user can't write model cache | Permission verification phase | `docker run --rm djok/facecraft:cpu whoami` returns `appuser`; all endpoints return 200 |
| Latest tag ambiguity | Docker Hub publish phase | No `:latest` tag visible on hub.docker.com/r/djok/facecraft |
| Lazy model load blocks first request | FastAPI lifespan startup phase | First request returns in <10s (not <90s) |
| Docker Hub README out of sync | Documentation publish phase | Hub description matches README.md after automated sync |

---

## Sources

- PyTorch CPU-only Docker optimization: https://shekhargulati.com/2025/02/05/reducing-size-of-docling-pytorch-docker-image/ (Feb 2025, verified CPU-only installation technique, 9.74GB → 1.74GB)
- PyTorch Docker 60% size reduction: https://mveg.es/posts/optimizing-pytorch-docker-images-cut-size-by-60percent/ (verified --no-cache-dir + base image selection, 7.6GB → 2.9GB)
- NVIDIA CUDA devel vs runtime vs base: https://forums.developer.nvidia.com/t/whats-the-difference-between-runtime-and-devel-docker/180288 (NVIDIA official forum)
- PyTorch CUDA in CPU image GitHub issue: https://github.com/pytorch/pytorch/issues/146786 (filed Feb 2025, confirmed active problem)
- rembg model path Docker deployment: https://github.com/danielgatis/rembg (official repo — `~/.u2net` default path documented)
- Docker Hub rate limits (effective April 1, 2025): https://docs.docker.com/docker-hub/usage/pulls/
- ML model health check patterns: https://apxml.com/courses/docker-for-ml-projects/chapter-5-containerizing-ml-inference/health-checks-inference
- FastAPI multi-worker model memory: https://github.com/fastapi/fastapi/discussions/7069 (confirmed linear RAM multiplication per worker)
- Docker build context .dockerignore: https://baeldung.com/ops/docker-reduce-build-context (245MB → 2.1MB example)
- Docker image tagging: https://www.docker.com/blog/docker-best-practices-using-tags-and-labels-to-manage-docker-image-sprawl/
- Python 3.11 + basicsr/facexlib compatibility: https://github.com/vladmandic/sdnext/discussions/110 (Python 3.11 was experimental for these libraries)
- Model download reproducibility: https://www.coguard.io/post/how-to-verify-your-downloads-in-docker-builds
- Non-root user Docker permissions: https://mydeveloperplanet.com/2022/10/19/docker-files-and-volumes-permission-denied/
- GitHub Actions Docker Hub push: https://docs.docker.com/build/ci/github-actions/ (official Docker docs)
- Existing codebase concerns: /home/rosen/facecraft/.planning/codebase/CONCERNS.md (internal audit, verified 2026-02-18)

---
*Pitfalls research for: Docker ML API packaging (Facecraft — CPU/GPU images, Docker Hub publishing)*
*Researched: 2026-02-18*
