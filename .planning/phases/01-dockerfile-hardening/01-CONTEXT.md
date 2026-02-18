# Phase 1: Dockerfile Hardening - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Patch the five concrete gaps in existing Dockerfiles so both images are correct and production-ready to build. Specifically: CPU-only PyTorch wheels, SHA256 model checksums, OCI standard labels, HEALTHCHECK, and .dockerignore. No new features — only hardening what exists.

</domain>

<decisions>
## Implementation Decisions

### Build transparency
- Silent by default — no output during successful checksum verification
- Output only on failure (checksum mismatch or download error)
- No summary line on success — Unix-style silence when everything is OK

### Checksum management
- SHA256 hashes stored inline in each Dockerfile as ARG values
- Hashes duplicated in both Dockerfile.cpu and Dockerfile.gpu (each file is self-contained)
- A `make update-checksums` Makefile target to automate hash updates: downloads models, computes SHA256, patches both Dockerfiles

### Image identity (OCI labels)
- License: MIT
- Source URL: https://github.com/djok/facecraft
- `.version` and `.description` labels included

### Claude's Discretion
- Error message format on checksum failure (expected vs actual hash detail level)
- Download retry behavior on network failure
- Version scheme (semver vs calver)
- Description text content
- Exact OCI label wording

</decisions>

<specifics>
## Specific Ideas

- Build output philosophy: "silent on success, loud on failure" — like Unix tools
- Each Dockerfile must be fully self-contained (no shared files for checksums)
- Makefile target preferred over standalone scripts for developer tooling

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-dockerfile-hardening*
*Context gathered: 2026-02-18*
