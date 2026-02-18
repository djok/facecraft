# External Integrations

**Analysis Date:** 2026-02-18

## APIs & External Services

**None detected** - This is a self-contained image processing service with no external API dependencies.

The application does not integrate with:
- Third-party APIs (no requests, httpx, or aiohttp imports)
- Cloud services (AWS, Google Cloud, Azure)
- AI/ML APIs (OpenAI, Anthropic, etc.)
- Analytics or monitoring services

## Data Storage

**Databases:**
- None - No database integration detected. No SQL, PostgreSQL, MongoDB, or Redis usage.

**File Storage:**
- Local filesystem only
  - Upload directory: `FACECRAFT_UPLOAD_DIR` (default: `/app/uploads`)
  - Output directory: `FACECRAFT_OUTPUT_DIR` (default: `/app/processed`)
  - Model directory: `FACECRAFT_MODELS_DIR` (default: `/app/models`)
  - Configuration: `src/facecraft/core/config.py`
  - Cleanup: Auto-deletion of files older than `FACECRAFT_CLEANUP_AGE_HOURS` (default: 24h)

**Caching:**
- In-memory only: Python `@lru_cache()` for settings at `src/facecraft/core/config.py`
- No distributed caching system

## Authentication & Identity

**Auth Provider:**
- None integrated
- Optional API key support: `FACECRAFT_API_KEY` environment variable exists but not enforced
- Location: `src/facecraft/core/config.py` (line 56)
- No authentication middleware currently active in `src/facecraft/main.py`

## Monitoring & Observability

**Error Tracking:**
- None - No error tracking service integrated

**Logs:**
- Standard Python logging via `print()` statements
- Log level configurable: `FACECRAFT_LOG_LEVEL` (default: INFO)
- No structured logging or log aggregation

**Health Checks:**
- `/health` - Basic liveness probe (always returns healthy)
- `/ready` - Readiness probe (checks if models are loaded)
- `/status` - Detailed status with device info, model status, and processing statistics
- Location: `src/facecraft/api/routes/health.py`

## CI/CD & Deployment

**Hosting:**
- Docker-based deployment (CPU and GPU variants)
- Dockerfile.cpu: `docker/Dockerfile.cpu`
- Dockerfile.gpu: `docker/Dockerfile.gpu`
- Multi-stage builds with model pre-downloading
- Non-root user (appuser) for security

**CI Pipeline:**
- None detected - No CI/CD configuration files (GitHub Actions, GitLab CI, etc.)

**Models:**
- Pre-downloaded at Docker build time (not fetched at runtime)
- dlib shape_predictor_68_face_landmarks.dat - Downloaded from dlib.net
- CodeFormer - Downloaded from GitHub releases
- rembg u2net_human_seg - Auto-downloaded via pip (cached in stage)
- Bundled in final image to avoid runtime downloads

## Environment Configuration

**Required env vars:**
- `FACECRAFT_HOST` (default: 0.0.0.0)
- `FACECRAFT_PORT` (default: 8000)
- `FACECRAFT_DEVICE` (default: auto) - Must be: auto, cpu, cuda, or cuda:0/1
- `FACECRAFT_MODELS_DIR` (default: /app/models) - Path to model directory
- `FACECRAFT_UPLOAD_DIR` (default: /app/uploads) - Temporary uploads
- `FACECRAFT_OUTPUT_DIR` (default: /app/processed) - Output files

**Processing options (env vars):**
- `FACECRAFT_DEFAULT_WIDTH` (default: 648)
- `FACECRAFT_DEFAULT_HEIGHT` (default: 648)
- `FACECRAFT_DEFAULT_BACKGROUND_R/G/B` (default: 240,240,240)
- `FACECRAFT_DEFAULT_FACE_MARGIN` (default: 0.3)
- `FACECRAFT_DEFAULT_OVAL_MASK` (default: true)
- `FACECRAFT_DEFAULT_ENHANCE_FIDELITY` (default: 0.7)
- `FACECRAFT_MAX_UPLOAD_SIZE_MB` (default: 20)
- `FACECRAFT_CLEANUP_AGE_HOURS` (default: 24)
- `FACECRAFT_MAX_CONCURRENT_JOBS` (default: 4)
- `FACECRAFT_BATCH_MAX_FILES` (default: 50)

**Secrets location:**
- `.env` file (not committed, see `.gitignore`)
- `.env.example` - Template with public defaults
- CORS origins: `FACECRAFT_CORS_ORIGINS` (default: * for open CORS)
- API key: `FACECRAFT_API_KEY` (optional, exists but not enforced)

## Webhooks & Callbacks

**Incoming:**
- None - No webhook endpoints defined

**Outgoing:**
- None - No external webhooks or callbacks

## File I/O & Model Loading

**Model Loading:**
- Synchronous loading on server startup via `init_processor()` at `src/facecraft/api/dependencies.py:18`
- Called in application lifespan at `src/facecraft/main.py:29`
- Models loaded once at startup, cached in global `_processor` variable
- Optional models gracefully degrade: face alignment and enhancement optional if models not found

**Processing Pipeline:**
1. Upload endpoint accepts file
2. Saved to `FACECRAFT_UPLOAD_DIR` with job ID prefix
3. Processed through 5 stages: face enhancement → detection → background removal → alignment → oval mask
4. Output saved to `FACECRAFT_OUTPUT_DIR/{job_id}/`
5. Both PNG (transparent) and JPEG (compressed) formats generated
6. Files available for download via `/api/v1/download/{job_id}/{format}`
7. Auto-cleanup after `FACECRAFT_CLEANUP_AGE_HOURS`

---

*Integration audit: 2026-02-18*
