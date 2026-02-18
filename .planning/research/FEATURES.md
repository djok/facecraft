# Feature Research

**Domain:** Docker ML API packaging and documentation — self-hosted AI image published to Docker Hub
**Researched:** 2026-02-18
**Confidence:** MEDIUM (WebSearch + official Docker docs verified; Docker Hub ML image conventions are community-standard rather than formally specified)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features every published Docker Hub ML image must have. Missing these means users bounce or open issues immediately.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Working `docker run` one-liner | First thing developers try; if this fails nothing else matters | LOW | Must use pre-pulled Hub tag, not local build. `docker run -p 8000:8000 djok/facecraft:cpu` |
| Separate `:cpu` and `:gpu` tags | GPU users need `--gpus all`; CPU users won't have NVIDIA runtime. Mixing breaks one group | LOW | Already planned. Tags `:cpu` and `:gpu` on Docker Hub |
| HEALTHCHECK instruction in Dockerfile | Orchestrators (Compose, Kubernetes) use this. Without it, container appears healthy before models load | LOW | Already in Dockerfiles. Verify `--start-period=120s` is long enough for cold start |
| Non-root USER in image | Security default. Developers flag images running as root in code review | LOW | Already in Dockerfiles (`appuser`, uid 1000) |
| All models bundled at build time (no runtime downloads) | The "zero-config" promise. If models download at startup, first run fails on restricted networks, and cold start is unpredictable | MEDIUM | Core requirement. Models ~615MB total baked into image |
| Environment variable configuration | Developers expect to configure without rebuilding. Port, workers, device are minimum | LOW | Already in Dockerfiles via `FACECRAFT_*` prefix |
| OCI standard image labels | `org.opencontainers.image.source`, `.version`, `.description`. Tools like Trivy, Dive, Harbor use these | LOW | Current labels are custom. Should switch to OCI spec |
| English README on Docker Hub | Docker Hub pulls description from README. Non-English README = image looks abandoned | LOW | Existing README is English but written for local build, not Hub pull |
| Swagger UI available at /docs | FastAPI default; developers expect interactive API docs without reading anything | LOW | Already present via FastAPI. Document the URL in README |
| docker-compose.yml in repo | Most developers use Compose for local dev. Without it, they write their own and get GPU config wrong | MEDIUM | Not yet present. Essential for GPU service definition |

### Differentiators (Competitive Advantage)

Features that distinguish Facecraft's Docker image from generic ML API images on Docker Hub.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Performance benchmarks in README | Concrete numbers (1.45s CPU, 0.43s GPU) let developers choose the right variant before pulling 16GB | LOW | Already measured. Add table to README prominently, near top |
| Single docker-compose.yml with CPU+GPU profiles | Developers don't have to maintain two files or remember which GPU flags to use. `--profile gpu` just works | MEDIUM | Use Compose `profiles:` to define both services in one file. GPU service adds `deploy.resources.reservations.devices` |
| Models section documenting what's bundled | Builds trust. Developers want to know exactly what's inside a 16GB image before pulling | LOW | List each model: name, size, source URL, purpose. Already partially in README |
| Quickstart that works in 60 seconds | Competitor images often have broken quick starts. Working curl examples copied verbatim builds reputation | LOW | README needs copy-paste-ready curl commands that hit the Hub image, not localhost from source |
| Image size transparency in README | 16.6GB CPU / 23.5GB is large but honest. Hiding it erodes trust when users see the pull size | LOW | Add size table with explanation of why (PyTorch + CUDA + models) |
| Volume mount example for uploads persistence | Stateless containers lose processed images on restart. Show `-v` flag for `/app/uploads` and `/app/processed` | LOW | One docker-compose volume section is enough |
| Multi-stage Dockerfile comments explaining each stage | Developers fork images. Commented Dockerfiles lower the barrier to customization | LOW | Current Dockerfiles have minimal comments on the model download stage logic |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem like good ideas but add complexity without proportionate value for this milestone.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Kubernetes manifests (Helm chart) | "Production ready" sounds like k8s | Adds a separate artifact to maintain; Compose is sufficient for the target (self-hosting developers); k8s users customize anyway | Provide docker-compose.yml with resource limits. Note k8s users can adapt it |
| Image size reduction below 5GB | Large images are complained about | PyTorch CPU-only is ~2.9GB, but dlib requires cmake build and CUDA adds 6GB. Aggressive slimming risks breaking the build or removing needed CUDA libs. Return on investment is low for this milestone | Document size rationale. Accept current size; optimize only if users report pull-time friction |
| Multi-architecture (arm64) support | M-series Macs are common | dlib compilation on arm64 with cmake is non-trivial; PyTorch arm64 wheels exist but CUDA doesn't apply; adds significant CI complexity. This is a separate milestone | Note in README that arm64 is not currently supported; point to native install as alternative |
| Automated GitHub Actions CI/CD for push-to-Hub | Looks professional | Out of scope for this milestone (PROJECT.md explicitly excludes CI/CD). Manual `docker build && docker push` is sufficient now | Note in README that builds are manual; CI/CD is a future milestone |
| Pinned digest tags (`:cpu@sha256:...`) | Reproducibility | Docker Hub free tier limits. Digest pinning is for enterprise pipelines. Target audience uses `:cpu`/`:gpu` | Use semantic version tags like `:1.0.0-cpu` alongside `:cpu` (latest). Digests come naturally |
| `.env` file for docker-compose secrets | Looks like security best practice | There are no secrets in Facecraft (it's a processing API, not a SaaS with API keys). Adding `.env` file management adds complexity with no security benefit | Keep environment variables inline in docker-compose.yml. Note in docs that no secrets are required |

---

## Feature Dependencies

```
[Working docker run one-liner]
    requires --> [All models bundled at build time]
    requires --> [Docker Hub image published with correct tags]

[docker-compose.yml CPU+GPU profiles]
    requires --> [Both :cpu and :gpu images published to Hub]
    enhances --> [Volume mount example for persistence]
    enhances --> [HEALTHCHECK]

[OCI standard image labels]
    requires --> [Dockerfile update]
    enhances --> [Docker Hub README description (version visible)]

[Performance benchmarks in README]
    enhances --> [Separate :cpu and :gpu tags] (gives users data to choose)

[Swagger UI at /docs]
    requires --> [Working docker run one-liner] (already running via FastAPI)
```

### Dependency Notes

- **Models bundled requires Dockerfile build-time download:** The model download stages in both Dockerfiles implement this. The build must succeed and models must be verified to load correctly (readiness endpoint `/ready` confirms this).
- **docker-compose.yml requires both images on Hub:** GPU profile only makes sense after `:gpu` is published. Write compose file targeting Hub images (`djok/facecraft:cpu`, `djok/facecraft:gpu`), not local builds.
- **OCI labels require Dockerfile edit:** Switch from current custom `LABEL` pairs to `org.opencontainers.image.*` prefix. Low-effort, high-signal.
- **Quickstart in README requires working Hub image:** README rewrite should happen after first successful push to Docker Hub so one-liners can be tested.

---

## MVP Definition

### Launch With (v1)

Minimum set to ship a professional Docker Hub presence for Facecraft.

- [ ] `djok/facecraft:cpu` published to Docker Hub — the product doesn't exist without this
- [ ] `djok/facecraft:gpu` published to Docker Hub — same rationale
- [ ] Working `docker run -p 8000:8000 djok/facecraft:cpu` verified end-to-end — core UX promise
- [ ] `docker-compose.yml` in repo root with CPU and GPU services (using Compose profiles) — GPU users need correct `deploy.resources` syntax
- [ ] README rewritten with: Hub one-liner, env var reference, model inventory, performance table, volume mount example — what developers read before trusting an image
- [ ] OCI standard labels in both Dockerfiles — takes 10 minutes, signals professionalism to tooling
- [ ] HEALTHCHECK verified (start-period adequate for model load time) — prevents false-healthy containers in Compose

### Add After Validation (v1.x)

- [ ] Semantic version tag (`:1.0.0-cpu`, `:1.0.0-gpu`) alongside `:cpu`/`:gpu` — add when publishing v1.1. Trigger: first breaking change or model update
- [ ] Volume mount examples tested and documented — trigger: first user question about persistence
- [ ] Dockerfile comments explaining each build stage — trigger: first fork or contributor PR

### Future Consideration (v2+)

- [ ] ARM64 image support — trigger: user requests from M-series Mac developers; requires CI/CD to be worthwhile
- [ ] GitHub Actions CI/CD for automated Hub pushes — trigger: second release. Manual push is fine for v1
- [ ] Image size optimization pass — trigger: user complaints about pull time. 16.6GB is large but honest

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Hub images published (`:cpu`, `:gpu`) | HIGH | MEDIUM (build + push) | P1 |
| Working `docker run` one-liner | HIGH | LOW (depends on Hub publish) | P1 |
| docker-compose.yml with GPU profile | HIGH | LOW | P1 |
| README rewrite (Hub-focused) | HIGH | LOW | P1 |
| OCI standard labels | MEDIUM | LOW | P1 |
| HEALTHCHECK validation | MEDIUM | LOW | P1 |
| Performance benchmarks in README | MEDIUM | LOW (already measured) | P1 |
| Models inventory in README | MEDIUM | LOW | P1 |
| Volume mount documentation | LOW | LOW | P2 |
| Semantic version tags | LOW | LOW | P2 |
| Dockerfile comments | LOW | LOW | P2 |
| ARM64 support | MEDIUM | HIGH | P3 |
| CI/CD pipeline | LOW | HIGH | P3 |
| Image size reduction | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

Examined: `onerahmet/openai-whisper-asr-webservice` (comparable self-hosted ML inference image), `linuxserver/faster-whisper` (professional Docker Hub image from a respected team), Ollama Docker image.

| Feature | whisper-asr-webservice | linuxserver/faster-whisper | Facecraft Target |
|---------|----------------------|---------------------------|-----------------|
| CPU one-liner | Yes, clean | Yes | Yes (MVP) |
| GPU one-liner | Yes, `--gpus all` flag | Yes, separate tag | Yes (MVP) |
| docker-compose example | No (gap in their docs) | Yes, full example | Yes (MVP — differentiator) |
| Models bundled | No — downloads at startup | No — downloads at startup | Yes (our differentiator) |
| Volume mount for model cache | Yes — primary UX for their model strategy | Yes | Not needed (models baked in) |
| Environment variable table | Yes | Yes | Yes (MVP) |
| Interactive API docs (/docs) | Yes (Swagger) | N/A (different protocol) | Yes (already working) |
| Performance benchmarks | No | No | Yes (differentiator — we have real numbers) |
| OCI labels | Not verified | Yes | Yes (MVP) |
| Separate CPU/GPU tags | Yes (`:latest`, `:latest-gpu`) | Yes | Yes (`:cpu`, `:gpu`) |
| Image size transparency | No | No | Yes (differentiator) |

**Key insight:** The most common gap across comparable images is the absence of docker-compose.yml examples with correct GPU syntax. Users consistently get `deploy.resources.reservations.devices` wrong. Providing a correct, tested compose file with both profiles is a genuine differentiator that saves a 30-minute debugging session.

**Second insight:** Bundling models at build time is rare — most comparable images download models on first run. This is Facecraft's strongest UX differentiator. The README must lead with this fact.

---

## Sources

- Docker Compose GPU support official docs: https://docs.docker.com/compose/how-tos/gpu-support/ (HIGH confidence — official)
- OCI image annotation spec: https://github.com/opencontainers/image-spec/blob/main/annotations.md (HIGH confidence — official)
- linuxserver/faster-whisper documentation: https://docs.linuxserver.io/images/docker-faster-whisper/ (MEDIUM confidence — comparable production image)
- Whisper ASR Webservice usage docs: https://ahmetoner.com/whisper-asr-webservice/run/ (MEDIUM confidence — comparable image, verified pattern)
- PyTorch Docker image size optimization: https://mveg.es/posts/optimizing-pytorch-docker-images-cut-size-by-60percent/ (MEDIUM confidence — technical blog, verified techniques)
- Docker Hub official images documentation: https://github.com/docker-library/docs (MEDIUM confidence — official)
- DataCamp Docker ML images overview: https://www.datacamp.com/blog/docker-container-images-for-machine-learning-and-ai (LOW confidence — editorial)

---
*Feature research for: Docker ML API packaging (Facecraft)*
*Researched: 2026-02-18*
