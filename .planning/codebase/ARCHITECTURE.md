# Architecture

**Analysis Date:** 2026-02-18

## Pattern Overview

**Overall:** Layered Pipeline Architecture with Dependency Injection

The Facecraft application follows a classic three-layer architecture with a clear separation between HTTP API, core processing logic, and external integrations. The design emphasizes composition over inheritance, using a modular pipeline pattern where each processing step is independently testable and replaceable.

**Key Characteristics:**
- **FastAPI-based REST API** for HTTP request handling and request/response validation
- **Dependency Injection** via FastAPI dependencies for loosely coupled components
- **Processing Pipeline** that chains multiple specialized modules sequentially
- **Stateless Request Handlers** that delegate to singleton processor instance
- **Model Lazy Loading** with graceful degradation (models optional but enhance results)

## Layers

**API Layer:**
- Purpose: Handle HTTP requests, validate input, manage file uploads/downloads, coordinate responses
- Location: `src/facecraft/api/`
- Contains: Route handlers, request/response schemas, dependency injection setup
- Depends on: Core configuration, processing layer
- Used by: HTTP clients (curl, Python requests, JavaScript fetch, etc.)

**Processing Layer:**
- Purpose: Implement the image transformation pipeline through composition of specialized modules
- Location: `src/facecraft/processing/`
- Contains: PhotoProcessor (orchestrator), BackgroundRemover, FaceDetector, FaceEnhancer, PhotoEnhancer
- Depends on: OpenCV, dlib, rembg, torch, torchvision, PIL, numpy
- Used by: API layer via dependency injection

**Core/Config Layer:**
- Purpose: Centralized configuration, exception definitions, application bootstrap
- Location: `src/facecraft/core/`
- Contains: Settings (Pydantic), custom exceptions, constants
- Depends on: Pydantic, Python stdlib
- Used by: All layers for configuration and error handling

## Data Flow

**Single Image Processing Flow:**

1. **HTTP POST to `/api/v1/process`** with multipart form data (image file + options)
2. **Route Handler** (`process.py:process_single_photo`) validates input and extracts options
3. **File Save** to temporary upload directory
4. **PhotoProcessor.process_image()** called with input path and output directory
5. **Processing Pipeline** (within PhotoProcessor):
   - Load image from disk via cv2
   - [Optional] FaceEnhancer.enhance() - applies CodeFormer for face restoration
   - FaceDetector.detect_face() - locates face rectangle in image
   - BackgroundRemover.remove_background() - removes background (u2net_human_seg)
   - [Optional] FaceDetector.align_face() - rotates face to frontal position
   - FaceDetector.crop_face() - centers face with margin
   - [Optional] PhotoEnhancer.enhance() - exposure, white balance, sharpening
   - [Optional] OvalMask.apply() - feathered oval mask for professional look
   - ImageResizer.resize_with_padding() - final size with background color/transparency
6. **Output Save** - generates PNG (transparent bg) and JPG (solid bg) variants
7. **Response** returned with job_id, processing time, file URLs, face detection metadata
8. **Cleanup** - uploaded temp file deleted; processed files kept for download

**Batch Processing Flow:**

1. Same as single image but repeated for each file in the batch
2. Each file processed independently with same options
3. Results collected with per-file success/failure status
4. Returns aggregated BatchResponse with per-file download URLs

**Quick Processing Flow (Process/Quick):**

1. Simplified version that accepts raw bytes instead of file
2. Uses sensible defaults (no options required)
3. Processes entirely in-memory with temporary file
4. Returns image bytes directly (PNG) instead of URLs

**State Management:**

- **Global Processor Instance**: Singleton `PhotoProcessor` created at startup via `dependencies.init_processor()` and cached globally
- **Model State**: Each model (face detector, background remover, etc.) loads on initialization and stays in memory for request reuse
- **Processing Statistics**: Counters maintained in PhotoProcessor.stats, accumulated across requests
- **Processing Times**: Last 100 processing times recorded for averaging statistics
- **Temporary Files**: Upload directory (`/app/uploads`) and output directory (`/app/processed`) managed by OS; old files auto-cleaned per configured age

## Key Abstractions

**PhotoProcessor:**
- Purpose: Orchestrates the complete processing pipeline
- Examples: `src/facecraft/processing/processor.py`
- Pattern: Facade pattern - combines multiple specialists into single unified interface; stores statistics; provides both file path and bytes-based processing

**ProcessingOptions:**
- Purpose: Immutable configuration object for a processing request
- Examples: Width, height, background color, face margin, enhancement flags
- Pattern: Data class with sensible defaults; passed through entire pipeline

**FaceDetector:**
- Purpose: Detects faces, extracts landmarks, aligns faces, crops face regions
- Examples: `src/facecraft/processing/face_detection.py`
- Pattern: Specialization - handles all face-related operations; lazy-loads optional shape predictor for alignment

**BackgroundRemover:**
- Purpose: AI-powered background segmentation and removal
- Examples: `src/facecraft/processing/background.py`
- Pattern: Wrapper around rembg library; converts between OpenCV (BGR/BGRA) and PIL (RGB/RGBA) formats

**PhotoEnhancer:**
- Purpose: Professional image enhancements (exposure, white balance, sharpening, contrast, saturation)
- Examples: `src/facecraft/processing/photo_enhancement.py`
- Pattern: Single-responsibility module; chains multiple OpenCV filters and PIL image enhancements

**FaceEnhancer:**
- Purpose: AI-powered face restoration using CodeFormer
- Examples: `src/facecraft/processing/face_enhancement.py`
- Pattern: Optional capability - gracefully degraded when model unavailable; improves face quality before detection

## Entry Points

**Application Entry:**
- Location: `src/facecraft/main.py`
- Triggers: Server startup (uvicorn)
- Responsibilities: Creates FastAPI app, configures CORS, registers routers, sets up lifespan events (model loading, file cleanup)

**Process Router (API):**
- Location: `src/facecraft/api/routes/process.py`
- Triggers: HTTP POST/GET/DELETE to `/api/v1/process*` endpoints
- Responsibilities: Validate requests, save uploads, call processor, format responses, manage file downloads

**Health Router (API):**
- Location: `src/facecraft/api/routes/health.py`
- Triggers: HTTP GET to `/health`, `/ready`, `/status` endpoints
- Responsibilities: Liveness/readiness checks, device info, model status, statistics reporting

**Application Startup:**
- Location: `src/facecraft/core/config.py` and `src/facecraft/main.py` lifespan
- Responsibilities: Load environment variables, initialize Settings, load models, cleanup old files

## Error Handling

**Strategy:** Exception-first with specific custom exceptions

**Patterns:**

- **Custom Exceptions**: Defined in `src/facecraft/core/exceptions.py`; hierarchy rooted at `FacecraftError`
  - `NoFaceDetectedError` - returned in ProcessResponse with error code, not HTTP exception
  - `InvalidImageError` - raised for corrupted/unreadable files
  - `ModelLoadError` - raised if model files missing (graceful degradation if optional)
  - `ImageProcessingError` - raised if processing pipeline fails
  - `FileTooLargeError` - raised if upload exceeds size limit

- **HTTP Exceptions**: FastAPI HTTPException raised for:
  - 400: Invalid format, no file provided, batch too large
  - 404: Job not found, output file not found
  - 500: File save failed, processing failed (internal errors)

- **Result Objects**: ProcessingResult.success + error fields returned for non-exception failures
  - `no_face_detected` error returned gracefully (common case, not exceptional)
  - Allows batch processing to continue even if individual files fail

- **Processor-Level Stats**: Maintains counters for total, success, no_face, errors for observability

## Cross-Cutting Concerns

**Logging:**
- Strategy: Print to stdout during startup/shutdown (configurable log level via `FACECRAFT_LOG_LEVEL`)
- Patterns: No structured logging library; simple print() statements in lifespan events
- Location: `src/facecraft/main.py` lifespan context manager
- Models may log warnings to stdout if optional components fail to load

**Validation:**
- Strategy: Pydantic V2 models for request/response validation; custom validators for settings
- Patterns: `ProcessingOptionsRequest` converted to `ProcessingOptions` for internal use; Settings uses field aliases and custom properties
- Location: `src/facecraft/api/schemas/` and `src/facecraft/core/config.py`
- File extensions validated in route handlers (whitelist: jpg, jpeg, png, bmp, webp)

**Authentication:**
- Strategy: Optional API key support (not enforced by default)
- Patterns: `FACECRAFT_API_KEY` env var can be set but no middleware currently validates it
- Location: `src/facecraft/core/config.py` settings
- Future: Would require custom FastAPI dependency for key validation

**Resource Management:**
- Strategy: Automatic cleanup via scheduled file deletion; graceful model loading
- Patterns:
  - Startup: `cleanup_old_files()` removes files older than `FACECRAFT_CLEANUP_AGE_HOURS` (default 24h)
  - Runtime: Models initialized once at startup, reused for all requests
  - Shutdown: Graceful cleanup (print statement only; models remain in memory)
  - Optional models: Available flags checked before use (face alignment, face enhancement)

**Performance Optimization:**
- Device Auto-Detection: `settings.get_device()` detects GPU availability at startup
- Model Lazy-Loading: Optional models (CodeFormer) only loaded if path exists
- Processing Statistics: Last 100 timings kept to avoid unbounded list growth
- Batch Processing: Sequential per-file (no parallelization yet), single job_id groups results
- Image Compression: Adaptive JPEG quality targeting max size (99KB default for AD compatibility)

---

*Architecture analysis: 2026-02-18*
