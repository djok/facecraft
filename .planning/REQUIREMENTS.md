# Requirements: Facecraft Docker Release

**Defined:** 2026-02-18
**Core Value:** User pulls Docker image and runs it — everything works immediately with zero configuration, zero internet downloads, zero manual model setup.

## v1 Requirements

Requirements for professional Docker Hub release. Each maps to roadmap phases.

### Dockerfiles

- [ ] **DOCK-01**: CPU Dockerfile uses CPU-only PyTorch wheels (`--extra-index-url https://download.pytorch.org/whl/cpu`) instead of CUDA-bundled wheels
- [ ] **DOCK-02**: All model downloads verified with SHA256 checksums at build time
- [ ] **DOCK-03**: Both Dockerfiles include OCI standard labels (`org.opencontainers.image.source`, `.version`, `.description`, `.licenses`)
- [ ] **DOCK-04**: `.dockerignore` properly configured to exclude `.planning/`, `.git/`, `tests/`, `__pycache__/`, `.env`, and other non-essential files
- [ ] **DOCK-05**: HEALTHCHECK instruction verified — start-period adequate for model load time, uses `/ready` endpoint
- [ ] **DOCK-06**: Models verified to load correctly inside container at build time (build fails if model download fails)

### Docker Compose

- [ ] **COMP-01**: Single `docker-compose.yml` in repo root with CPU and GPU services using Compose profiles (`--profile cpu` / `--profile gpu`)
- [ ] **COMP-02**: GPU service includes correct `deploy.resources.reservations.devices` syntax for NVIDIA GPU passthrough
- [ ] **COMP-03**: Volume mounts configured for `/app/uploads` and `/app/processed` persistence
- [ ] **COMP-04**: Environment variables documented inline with sensible defaults

### Documentation

- [ ] **DOCS-01**: README.md rewritten in English with Hub-pull quickstart (`docker run -p 8000:8000 djok/facecraft:cpu`)
- [ ] **DOCS-02**: README includes environment variable reference table (all `FACECRAFT_*` vars with defaults and descriptions)
- [ ] **DOCS-03**: README includes bundled models inventory (name, size, source, purpose for each model)
- [ ] **DOCS-04**: README includes CPU vs GPU performance benchmark table
- [ ] **DOCS-05**: README includes volume mount examples for data persistence
- [ ] **DOCS-06**: README includes API endpoint overview with curl examples
- [ ] **DOCS-07**: README includes image size transparency (size, breakdown, why it's large)

### Publishing

- [ ] **PUBL-01**: CPU image built and pushed to `djok/facecraft:cpu` on Docker Hub
- [ ] **PUBL-02**: GPU image built and pushed to `djok/facecraft:gpu` on Docker Hub
- [ ] **PUBL-03**: Docker Hub repository description synced from README.md
- [ ] **PUBL-04**: Smoke test passes — pulled image starts, `/health` returns 200, processes a test image successfully

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### CI/CD

- **CICD-01**: GitHub Actions workflow for automated Docker Hub push on tag
- **CICD-02**: Automated image size tracking in CI

### Multi-Architecture

- **ARCH-01**: ARM64 (Apple Silicon) image support
- **ARCH-02**: Multi-arch manifest (`docker manifest create`)

### Versioning

- **VERS-01**: Semantic version tags (`:1.0.0-cpu`, `:1.0.0-gpu`) alongside `:cpu`/`:gpu`

## Out of Scope

| Feature | Reason |
|---------|--------|
| Kubernetes manifests / Helm chart | Compose is sufficient for target audience; k8s users customize anyway |
| Image size reduction below current | PyTorch + models dominate size; ROI too low for this milestone |
| Code refactoring (logging, async) | Separate milestone; not packaging concern |
| New API features | Packaging-only milestone |
| `.env` file for Compose secrets | No secrets in Facecraft; adds unnecessary complexity |
| ARM64 / multi-arch support | dlib arm64 compilation is non-trivial; separate milestone |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DOCK-01 | Phase 1 | Pending |
| DOCK-02 | Phase 1 | Pending |
| DOCK-03 | Phase 1 | Pending |
| DOCK-04 | Phase 1 | Pending |
| DOCK-05 | Phase 1 | Pending |
| DOCK-06 | Phase 1 | Pending |
| COMP-01 | Phase 2 | Pending |
| COMP-02 | Phase 2 | Pending |
| COMP-03 | Phase 2 | Pending |
| COMP-04 | Phase 2 | Pending |
| DOCS-01 | Phase 3 | Pending |
| DOCS-02 | Phase 3 | Pending |
| DOCS-03 | Phase 3 | Pending |
| DOCS-04 | Phase 3 | Pending |
| DOCS-05 | Phase 3 | Pending |
| DOCS-06 | Phase 3 | Pending |
| DOCS-07 | Phase 3 | Pending |
| PUBL-01 | Phase 3 | Pending |
| PUBL-02 | Phase 3 | Pending |
| PUBL-03 | Phase 3 | Pending |
| PUBL-04 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0

---
*Requirements defined: 2026-02-18*
*Last updated: 2026-02-18 after roadmap creation*
