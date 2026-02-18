# Milestones

## v1.0 Professional Docker Release (Shipped: 2026-02-18)

**Phases completed:** 3 phases, 7 plans
**Timeline:** 18 days (2026-01-31 → 2026-02-18)
**Files modified:** 44 files, 7,293 insertions

**Key accomplishments:**
- Hardened CPU + GPU Dockerfiles with CPU-only PyTorch wheels, SHA256 model checksums, OCI labels, HEALTHCHECK
- Built and verified both images — air-gap self-containment proven, non-root execution (appuser)
- Docker Compose with CPU/GPU profiles, named volumes, GPU device reservation
- Published `djok/facecraft:cpu` (4.08 GB) and `:gpu` (13.8 GB) to Docker Hub
- Rewrote README.md Hub-first with complete env var reference (26 vars), benchmarks, API docs
- Smoke test script proving end-to-end: pull → start → /health 200 → image processing → valid PNG

**Deferred:** Docker Hub description sync (PUBL-03) — manual step, can be done later

---

