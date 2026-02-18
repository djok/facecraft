---
phase: 01-dockerfile-hardening
plan: 01
subsystem: infra
tags: [docker, pytorch, sha256, oci-labels, healthcheck]

requires:
  - phase: none
    provides: "First phase - no dependencies"
provides:
  - "Hardened CPU Dockerfile with CPU-only PyTorch wheels"
  - "SHA256 checksum verification for all bundled models"
  - "OCI standard image labels"
  - "Readiness-based HEALTHCHECK"
affects: [phase-02-build-verify]

tech-stack:
  added: []
  patterns:
    - "SHA256 checksum verification with sha256sum -c --quiet"
    - "OCI standard labels (org.opencontainers.image.*)"
    - "CPU-only PyTorch via --extra-index-url"

key-files:
  created: []
  modified:
    - docker/Dockerfile.cpu

key-decisions:
  - "Used --extra-index-url (not --index-url) to preserve PyPI access for non-PyTorch packages"
  - "Computed real SHA256 hashes from live model downloads instead of using placeholders"
  - "Verify checksum of uncompressed .dat file for shape predictor (after bunzip2)"

patterns-established:
  - "Silent on success, loud on failure: sha256sum -c --quiet"
  - "Model checksums as ARG values in model-downloader stage"

duration: 3min
completed: 2026-02-18
---

# Phase 01 Plan 01: Patch Dockerfile.cpu Summary

**CPU-only PyTorch wheels via --extra-index-url, SHA256 checksum verification for 3 models, OCI labels, HEALTHCHECK targeting /ready**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-18T11:59:08Z
- **Completed:** 2026-02-18T12:02:28Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- CPU Dockerfile now uses `--extra-index-url https://download.pytorch.org/whl/cpu` to pull torch 2.0.1+cpu (eliminates ~1.8GB CUDA bloat)
- All 3 model downloads verified with live-computed SHA256 checksums (shape predictor, CodeFormer, u2net_human_seg)
- Legacy LABEL replaced with OCI standard `org.opencontainers.image.*` labels (source, version, description, licenses, title, vendor)
- HEALTHCHECK updated from `/health` to `/ready` with 180s start-period for model-aware readiness

## Task Commits

Each task was committed atomically:

1. **Task 1+2: Harden Dockerfile.cpu** - `5aa5967` (feat)

**Plan metadata:** committed with plan execution

## Files Created/Modified
- `docker/Dockerfile.cpu` - Added CPU wheel index, SHA256 checksums, OCI labels, updated HEALTHCHECK

## Decisions Made
- Used `--extra-index-url` instead of `--index-url` to preserve PyPI access for non-PyTorch packages like fastapi, dlib, etc.
- Computed real SHA256 hashes by downloading all 3 models live rather than using placeholders
- Verified checksum of uncompressed `.dat` file for dlib shape predictor (post-bunzip2), since that's the artifact copied to final image

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Computed real SHA256 hashes instead of placeholders**
- **Found during:** Task 1 (SHA256 checksums)
- **Issue:** Plan suggested using placeholder values; real hashes provide immediate build verification
- **Fix:** Downloaded all 3 models, computed SHA256 hashes, embedded real values
- **Files modified:** docker/Dockerfile.cpu
- **Verification:** Hashes match live downloads
- **Committed in:** 5aa5967

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Positive improvement - real hashes instead of placeholders means builds work immediately

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CPU Dockerfile fully hardened, ready for Phase 2 build verification
- SHA256 hashes computed and embedded for all 3 models

---
*Phase: 01-dockerfile-hardening*
*Completed: 2026-02-18*
