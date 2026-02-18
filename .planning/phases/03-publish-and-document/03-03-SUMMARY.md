---
phase: 03-publish-and-document
plan: 03
subsystem: testing
tags: [smoke-test, docker, docker-hub, health-check, e2e-validation]

# Dependency graph
requires:
  - phase: 03-publish-and-document
    provides: "Published djok/facecraft:cpu and djok/facecraft:gpu on Docker Hub"
  - phase: 03-publish-and-document
    provides: "Hub-first README.md with quickstart and API documentation"
provides:
  - "Reusable smoke test script (scripts/smoke-test.sh) for validating pulled Docker Hub images"
  - "End-to-end verification that djok/facecraft:cpu works from pull to image processing"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: ["Smoke test with health-check retry loop and cleanup trap"]

key-files:
  created:
    - "scripts/smoke-test.sh"
  modified: []

key-decisions:
  - "Hub description sync deferred -- Docker Hub API requires separate JWT auth beyond docker login, user chose to skip"
  - "Smoke test uses real portrait download from thispersondoesnotexist.com for face detection validation"

patterns-established:
  - "Smoke test pattern: pull -> run -> health wait -> functional test -> cleanup"

# Metrics
duration: 3min
completed: 2026-02-18
---

# Phase 3 Plan 3: Smoke Test and Hub Sync Summary

**Smoke test script validates pulled djok/facecraft:cpu end-to-end -- health check in 35s, image processing returns valid 58 KB PNG; Hub description sync deferred**

## Performance

- **Duration:** 3 min (finalization only; Task 1 executed in prior session)
- **Started:** 2026-02-18 (Task 1 executed in prior session)
- **Completed:** 2026-02-18
- **Tasks:** 1 completed, 1 skipped (2 total)
- **Files modified:** 1

## Accomplishments

- Created `scripts/smoke-test.sh` -- self-contained smoke test that pulls a Docker Hub image, starts it, waits for /health, tests /api/v1/process/quick, and cleans up
- Ran smoke test against `djok/facecraft:cpu` from Docker Hub: /health returned 200 in 35 seconds, image processing returned a valid PNG (58,089 bytes)
- Proved the published CPU image works end-to-end for a real user workflow (pull, start, health check, process image)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create smoke test script and run against pulled CPU image** - `3b557b8` (feat)
2. **Task 2: Sync README to Docker Hub description** - SKIPPED (user deferred; Hub API requires separate JWT auth)

## Files Created/Modified

- `scripts/smoke-test.sh` - Executable smoke test script: pulls Docker Hub image, starts container, waits for /health with retry loop (max 300s), POSTs test portrait to /api/v1/process/quick, validates PNG output, cleans up container

## Decisions Made

- Hub description sync (Task 2) deferred by user choice -- Docker Hub API requires a separate JWT obtained via username/password authentication, which is distinct from `docker login` credentials. User was already authenticated via `docker login` but declined to enter credentials again for the Hub API. This can be done manually at any time using the instructions in the plan.
- Smoke test uses a real portrait image to validate face detection, not a synthetic placeholder

## Deviations from Plan

None -- plan executed as written. Task 2 was a checkpoint:human-action that the user elected to skip (an explicitly supported option per the plan instructions).

## Issues Encountered

- Docker Hub description sync requires a separate JWT token obtained via the Hub API (`hub.docker.com/v2/users/login/`), which is distinct from `docker login` authentication. This was anticipated in the plan design (Task 2 was a human-action checkpoint with an explicit "skip" option).

## User Setup Required

**Optional: Docker Hub description sync.** To update the Hub overview page with README.md content, run:

```bash
# Get JWT token (replace YOUR_PASSWORD with Docker Hub password or PAT)
TOKEN=$(curl -s -H "Content-Type: application/json" \
  -X POST -d '{"username":"djok","password":"YOUR_PASSWORD"}' \
  https://hub.docker.com/v2/users/login/ | jq -r .token)

# Sync README
README_JSON=$(jq -Rs . < README.md)
curl -s -X PATCH -L \
  "https://hub.docker.com/v2/repositories/djok/facecraft/" \
  -H "Content-Type: application/json" \
  -H "Authorization: JWT ${TOKEN}" \
  -d "{\"description\":\"AI portrait processing API - background removal, face detection, alignment, enhancement\",\"full_description\":${README_JSON}}"
```

Verify at: https://hub.docker.com/r/djok/facecraft

## Next Phase Readiness

- This is the final plan of the final phase. The project is complete.
- All three phases delivered: containerization (Phase 1), build/orchestration (Phase 2), publish/document (Phase 3)
- Published images are verified working end-to-end via smoke test
- Smoke test script is committed for future CI/CD use

## Self-Check: PASSED

- [x] `scripts/smoke-test.sh` exists and is executable
- [x] `03-03-SUMMARY.md` exists at `.planning/phases/03-publish-and-document/03-03-SUMMARY.md`
- [x] Commit `3b557b8` exists in git log

---
*Phase: 03-publish-and-document*
*Completed: 2026-02-18*
