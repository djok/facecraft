# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-18)

**Core value:** User pulls the Docker image and runs it — everything works immediately with zero configuration, zero internet downloads, zero manual model setup.
**Current focus:** Phase 3 in progress — Publish and Document

## Current Position

Phase: 3 of 3 (Publish and Document)
Plan: 3 of 3 in current phase (03-01 and 03-02 complete)
Status: Both Docker images pushed to Docker Hub and manifest-verified. Plan 03-03 (smoke test) remaining.
Last activity: 2026-02-18 — Plan 03-01 complete: CPU and GPU images published to Docker Hub

Progress: [█████████░] 90%

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: 5.3 min
- Total execution time: 32 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 2 | 5 min | 2.5 min |
| 2 | 2 | 15 min | 7.5 min |
| 3 | 2 | 12 min | 6 min |

**Recent Trend:**
- Last 5 plans: 2min, 12min, 3min, 2min, 10min
- Trend: Docker push (10 min) dominated by upload time for 13.8 GB GPU image

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Phase 1: PyTorch must stay pinned at `torch==2.0.1` + `torchvision==0.15.2` — `basicsr==1.4.2` breaks on torchvision 0.16+; do not upgrade
- Phase 1: GPU base image kept at CUDA 12.1.0 — research confirmed PyTorch 2.0.1 only has cu118 wheels, upgrading base provides no benefit
- Phase 1: HEALTHCHECK must use `/ready` endpoint with `--start-period=180s` minimum
- All phases: Never push `:latest` tag — only `:cpu` and `:gpu`
- Phase 2: No `version:` key in docker-compose.yml — obsolete since Compose v2.25.0
- Phase 2: Both services profiled (no always-on service) to prevent port 8000 conflicts
- Phase 2: Compose healthcheck targets `/health` (liveness); Dockerfile HEALTHCHECK targets `/ready` (readiness)
- Phase 2: CPU service uses `FACECRAFT_DEVICE: "cpu"` (forced), GPU uses `"auto"` (detects GPU)
- Phase 3: README env vars grouped into 6 logical categories (Server, Device, Model Paths, Processing Defaults, Storage, Limits, Security)
- Phase 3: Hub-first README structure — docker run one-liner within first 10 lines, build instructions in Development section
- Phase 3: README kept at 9.2 KB for Docker Hub full_description compatibility (limit 25 KB)
- Phase 3: No :latest tag pushed -- only :cpu and :gpu per locked decision; pre-existing :latest on Hub left untouched

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 1: SHA256 hashes computed and embedded in both Dockerfiles (resolved)
- Phase 2: Image sizes measured — CPU 4.08 GB (under 8 GB target), GPU 13.8 GB (slightly over 12 GB target, accepted as informational)

## Session Continuity

Last session: 2026-02-18
Stopped at: Completed 03-01-PLAN.md (Docker Hub publish). Plan 03-03 remaining.
Resume file: None
