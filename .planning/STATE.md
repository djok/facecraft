# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-18)

**Core value:** User pulls the Docker image and runs it — everything works immediately with zero configuration, zero internet downloads, zero manual model setup.
**Current focus:** Phase 2 complete — Build, Verify, and Orchestrate

## Current Position

Phase: 2 of 3 (Build, Verify, and Orchestrate) -- COMPLETE
Plan: 2 of 2 in current phase (all complete)
Status: Phase 2 fully complete. Both Docker images built, verified, and orchestrated with docker-compose.yml.
Last activity: 2026-02-18 — Phase 2 complete: docker-compose.yml validated, CPU /health returns 200

Progress: [███████░░░] 70%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: 5 min
- Total execution time: 20 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 2 | 5 min | 2.5 min |
| 2 | 2 | 15 min | 7.5 min |

**Recent Trend:**
- Last 5 plans: 3min, 2min, 12min, 3min
- Trend: Docker builds are the time-intensive step; compose creation fast

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

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 1: SHA256 hashes computed and embedded in both Dockerfiles (resolved)
- Phase 2: Image sizes measured — CPU 4.08 GB (under 8 GB target), GPU 13.8 GB (slightly over 12 GB target, accepted as informational)

## Session Continuity

Last session: 2026-02-18
Stopped at: Phase 2 execution complete. Ready for Phase 3.
Resume file: None
