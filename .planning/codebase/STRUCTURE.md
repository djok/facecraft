# Codebase Structure

**Analysis Date:** 2026-02-18

## Directory Layout

```
facecraft/
├── src/facecraft/                 # Main package directory
│   ├── __init__.py               # Package metadata (version, author)
│   ├── main.py                   # FastAPI application entry point
│   ├── core/                     # Configuration and exceptions
│   │   ├── __init__.py
│   │   ├── config.py             # Pydantic Settings, environment variables
│   │   └── exceptions.py         # Custom exception hierarchy
│   ├── api/                      # HTTP API layer
│   │   ├── __init__.py
│   │   ├── dependencies.py       # FastAPI dependency injection (processor, dirs, cleanup)
│   │   ├── routes/               # Route handlers
│   │   │   ├── __init__.py
│   │   │   ├── health.py         # /health, /ready, /status endpoints
│   │   │   └── process.py        # /api/v1/process* endpoints (single, quick, batch)
│   │   └── schemas/              # Pydantic models for requests/responses
│   │       ├── __init__.py
│   │       ├── requests.py       # ProcessingOptionsRequest, component options
│   │       └── responses.py      # ProcessResponse, StatusResponse, HealthResponse, etc.
│   └── processing/               # Image processing pipeline
│       ├── __init__.py
│       ├── processor.py          # PhotoProcessor (main orchestrator)
│       ├── background.py         # BackgroundRemover (rembg wrapper)
│       ├── face_detection.py     # FaceDetector (dlib-based)
│       ├── face_enhancement.py   # FaceEnhancer (CodeFormer)
│       └── photo_enhancement.py  # PhotoEnhancer, OvalMask, ImageResizer
├── docker/                       # Docker build configurations
│   ├── Dockerfile.cpu            # CPU-optimized image (python:3.11-slim)
│   └── Dockerfile.gpu            # GPU-optimized image (nvidia/cuda:12.1)
├── tests/                        # Test directory (structure mirrors src/)
├── pyproject.toml               # Project metadata, dependencies, tool configs
├── requirements.txt             # Core dependencies
├── requirements-gpu.txt         # Additional GPU dependencies
├── .env.example                 # Environment variable template
├── README.md                    # Documentation
└── LICENSE                      # MIT License
```

## Directory Purposes

**src/facecraft/:**
- Purpose: Main Python package containing all source code
- Contains: Modules organized by layer (core, api, processing)
- Key files: `__init__.py` with version, `main.py` for app entry

**core/:**
- Purpose: Cross-cutting configuration and error handling
- Contains: Settings object with env var support, custom exception classes
- Key files: `config.py` (Settings with Pydantic), `exceptions.py` (FacecraftError hierarchy)

**api/:**
- Purpose: HTTP request handling and response formatting
- Contains: Route handlers, API schemas (Pydantic models), dependency injection setup
- Key files: `routes/process.py` (main API endpoints), `schemas/` (request/response models), `dependencies.py` (processor initialization)

**api/routes/:**
- Purpose: FastAPI route handlers grouped by domain
- Contains: Endpoint implementations with docstrings, parameter validation, response formatting
- Key files: `process.py` (process, quick, batch, download, cleanup endpoints), `health.py` (health, ready, status probes)

**api/schemas/:**
- Purpose: Request/response validation and serialization
- Contains: Pydantic V2 BaseModel classes with field validators and properties
- Key files: `requests.py` (ProcessingOptionsRequest, BackgroundOptions, FaceOptions), `responses.py` (ProcessResponse, StatusResponse, etc.)

**processing/:**
- Purpose: Image transformation pipeline implementation
- Contains: Modular processors for each stage (background removal, face detection, enhancement)
- Key files: `processor.py` (PhotoProcessor facade), specialized modules for each processing step

**docker/:**
- Purpose: Container image definitions
- Contains: Multi-stage Dockerfiles for CPU and GPU variants with model downloads
- Key files: `Dockerfile.cpu` (standard deployment), `Dockerfile.gpu` (CUDA acceleration)

## Key File Locations

**Entry Points:**
- `src/facecraft/main.py`: FastAPI app creation, lifespan context manager, router registration
- `src/facecraft/__init__.py`: Package metadata (version "1.0.0", author "OBVT Toolbox")
- `pyproject.toml` project.scripts: `facecraft = "facecraft.main:app"` defines CLI entry point

**Configuration:**
- `src/facecraft/core/config.py`: Settings class with FACECRAFT_* env var support, device detection, model path resolution
- `.env.example`: Template for environment variables (not committed with actual secrets)
- `pyproject.toml`: Project metadata, dependencies, build system, tool configurations (ruff, black, mypy, pytest)

**Core Logic:**
- `src/facecraft/processing/processor.py`: PhotoProcessor (320 lines) - orchestrates entire pipeline, manages stats
- `src/facecraft/processing/background.py`: BackgroundRemover - wraps rembg for u2net_human_seg model
- `src/facecraft/processing/face_detection.py`: FaceDetector - dlib-based detection, alignment, cropping
- `src/facecraft/processing/face_enhancement.py`: FaceEnhancer - CodeFormer integration
- `src/facecraft/processing/photo_enhancement.py`: PhotoEnhancer, OvalMask, ImageResizer - filters and output formatting

**API Routes:**
- `src/facecraft/api/routes/process.py`: POST /api/v1/process, /api/v1/process/quick, /api/v1/process/batch; GET /api/v1/download/{job_id}/{format}; DELETE /api/v1/jobs/{job_id}
- `src/facecraft/api/routes/health.py`: GET /health, /ready, /status endpoints

**Testing:**
- `tests/`: Directory structure mirrors `src/` (implied by pyproject.toml testpaths)
- Test commands: `pytest tests/ -v`, `pytest tests/ --cov` for coverage

## Naming Conventions

**Files:**
- `snake_case.py` for all modules
- Pattern examples:
  - `processor.py` - main orchestrator
  - `face_detection.py` - domain-specific module
  - `photo_enhancement.py` - domain-specific module
  - `process.py` - routes file
  - `health.py` - routes file
  - `requests.py`, `responses.py` - schema files

**Directories:**
- `snake_case/` for all package directories
- Pattern examples:
  - `api/` - layer directory
  - `routes/` - subdivision within api
  - `schemas/` - subdivision within api
  - `processing/` - layer directory
  - `core/` - layer directory

**Classes:**
- `PascalCase` for all classes
- Pattern examples:
  - `PhotoProcessor` - main orchestrator class
  - `FaceDetector` - specialist module class
  - `BackgroundRemover` - specialist module class
  - `ProcessingOptions` - dataclass for configuration
  - `ProcessingResult` - dataclass for results
  - `Settings` - Pydantic settings class

**Functions:**
- `snake_case` for all functions
- Pattern examples:
  - `get_processor()` - dependency injection provider
  - `process_image()` - main processing method
  - `detect_face()` - specialist method
  - `remove_background()` - specialist method
  - `enhance()` - enhancement method

**Constants:**
- ALL_CAPS for module-level constants
- Pattern: Not extensively used; defaults in Pydantic models instead
- Example: Default file extensions `{'.jpg', '.jpeg', '.png', '.bmp', '.webp'}` defined inline in routes

## Where to Add New Code

**New Feature (e.g., new processing step):**
- Primary code: `src/facecraft/processing/{new_module}.py` - create new class inheriting from or following pattern of existing processors
- Integration point: `src/facecraft/processing/processor.py` - add new module instance in `__init__`, call in pipeline
- Tests: `tests/processing/test_{new_module}.py` - unit tests for new class
- Example flow: Add FaceBlurring -> `src/facecraft/processing/face_blurring.py` -> instantiate in processor -> call in process_image pipeline

**New API Endpoint:**
- Route handler: `src/facecraft/api/routes/{domain}.py` - add @router.post/get/delete endpoint
- Request schema: `src/facecraft/api/schemas/requests.py` - add Pydantic model if needed
- Response schema: `src/facecraft/api/schemas/responses.py` - add Pydantic model if needed
- Register router: `src/facecraft/main.py` - include_router() call
- Tests: `tests/api/routes/test_{domain}.py` - test endpoint behavior
- Example: Add bulk download -> create `bulk_download()` route in routes, register in main.py

**New Configuration Option:**
- Settings: `src/facecraft/core/config.py` - add Field() with default and FACECRAFT_* alias
- Usage in code: Use `settings.{new_option}` via dependency injection
- Environment variable: FACECRAFT_{NEW_OPTION} automatically supported
- Example: Add `processing_concurrency` -> Field() in Settings -> use in processor

**Utilities/Helpers:**
- Shared helpers: `src/facecraft/processing/photo_enhancement.py` already contains OvalMask, ImageResizer utility classes
- New utility class: Can extend photo_enhancement.py or create `src/facecraft/processing/utils.py`
- Shared validation: Keep in request schemas or add to core/

**Error Handling:**
- Custom exceptions: `src/facecraft/core/exceptions.py` - add new exception class inheriting from FacecraftError
- Route-level handling: In route handlers, catch and return ProcessResponse with error field (not HTTPException for expected errors)
- Processor-level: Return ProcessingResult(success=False, error=...) for non-exceptional failures

## Special Directories

**docker/:**
- Purpose: Container image definitions
- Generated: No (manual Dockerfiles)
- Committed: Yes (version-controlled in repo)
- Contains: Dockerfile.cpu, Dockerfile.gpu with multi-stage builds, model downloads, uvicorn entrypoints

**/app/uploads (runtime only):**
- Purpose: Temporary storage for uploaded files during processing
- Generated: Yes (created at runtime by API route handlers)
- Committed: No (gitignore'd, ephemeral)
- Created by: `get_upload_dir()` dependency, path configured via FACECRAFT_UPLOAD_DIR env var
- Cleanup: Manual via upload_path.unlink() after processing, or auto-cleanup of old files via cleanup_old_files()

**/app/processed (runtime only):**
- Purpose: Storage for processed output images (PNG and JPG variants)
- Generated: Yes (created at runtime during processing)
- Committed: No (gitignore'd, ephemeral)
- Created by: `get_output_dir()` dependency, path configured via FACECRAFT_OUTPUT_DIR env var
- Structure: `{output_dir}/{job_id}/{filename}.png` and `{output_dir}/{job_id}/jpg/{filename}.jpg`
- Cleanup: Manual via shutil.rmtree() on DELETE /api/v1/jobs/{job_id}, or auto-cleanup via cleanup_old_files()

**.planning/codebase/:**
- Purpose: GSD mapping documents (architecture, structure, conventions, etc.)
- Generated: Yes (created by GSD tools)
- Committed: Yes (reference for future phases)
- Files: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, etc.

---

*Structure analysis: 2026-02-18*
