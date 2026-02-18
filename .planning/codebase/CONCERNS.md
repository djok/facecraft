# Codebase Concerns

**Analysis Date:** 2026-02-18

## Tech Debt

**Excessive print() statements instead of structured logging:**
- Issue: The codebase uses `print()` for all logging instead of a proper logging framework. This makes debugging harder in production and prevents log level filtering.
- Files: `src/facecraft/main.py` (lines 22-43), `src/facecraft/processing/face_detection.py` (line 28), `src/facecraft/processing/face_enhancement.py` (lines 70, 149), `src/facecraft/api/dependencies.py`
- Impact: Production logs are unstructured, cannot be filtered by severity, and cannot be routed to log aggregation systems. All startup/shutdown messages go to stdout regardless of log level.
- Fix approach: Replace `print()` with Python's `logging` module. Use `logging.getLogger(__name__)` per module and configure a root logger in `src/facecraft/main.py` that respects `FACECRAFT_LOG_LEVEL` setting.

**Global mutable state in dependencies:**
- Issue: `src/facecraft/api/dependencies.py` uses module-level global variables (`_processor`, `_start_time`, `_processing_times`) to maintain state across requests.
- Files: `src/facecraft/api/dependencies.py` (lines 12-15)
- Impact: Thread safety concerns in concurrent request handling. Multiple workers could race on `_processing_times` list. Global state makes testing difficult.
- Fix approach: Store statistics in the `PhotoProcessor` instance itself instead of module globals. Use thread-safe data structures (Queue, Lock) if multi-worker stats tracking is needed.

**Bare exception catching with minimal context:**
- Issue: Multiple catch-all `except Exception` blocks that swallow errors and rely on downstream code to detect failures.
- Files: `src/facecraft/processing/face_enhancement.py` (line 69), `src/facecraft/processing/processor.py` (line 190), `src/facecraft/processing/face_detection.py` (line 27)
- Impact: Errors during initialization are silently ignored (e.g., CodeFormer model load fails but no error is propagated). Processing exceptions converted to generic strings lose stack trace context.
- Fix approach: Use specific exception types, log full stack traces with `logging.exception()`, and propagate critical errors from initialization.

**No input validation on file uploads:**
- Issue: File validation only checks extension and saves file before processing. No validation of file size, magic bytes, or image dimensions before processing.
- Files: `src/facecraft/api/routes/process.py` (lines 74-90)
- Impact: Malformed files consume memory/disk. Size limit is enforced at FastAPI level but not explicitly validated per user. Large PNG files could bypass JPEG size limits.
- Fix approach: Validate file using magic bytes library. Check image dimensions before processing. Validate file size explicitly in route handler.

## Known Bugs

**Face detection returns largest face silently:**
- Symptoms: When multiple faces are detected, the largest one is processed without user notification.
- Files: `src/facecraft/processing/face_detection.py` (lines 57-61)
- Trigger: Upload image with multiple people/faces
- Workaround: Crop image to single face before upload; API returns no indication that multiple faces were present.
- Impact: Users expect single portrait processing but get wrong face if group photo is uploaded.

**Cleanup task could delete files still being downloaded:**
- Symptoms: User starts download, cleanup task deletes file between `exists()` check and `read()` call.
- Files: `src/facecraft/api/routes/process.py` (lines 228-242), `src/facecraft/api/dependencies.py` (lines 86-101)
- Trigger: Cleanup runs while file is being downloaded (24-hour window by default)
- Impact: Download returns 404 after appearing to exist. Race condition on shared filesystem.
- Workaround: None - download must complete before cleanup interval.

**Batch processing file paths not validated against traversal:**
- Symptoms: Job ID used directly in path construction.
- Files: `src/facecraft/api/routes/process.py` (lines 304-311)
- Trigger: Potential path traversal if job_id is malicious (e.g., "../../../etc/passwd")
- Impact: Could read/write outside intended directories, though FastAPI's UUID generation mitigates this.
- Workaround: None needed - UUID format prevents traversal, but explicit validation is better practice.

## Security Considerations

**Unlimited CORS origins by default:**
- Risk: CORS is configured with `allow_origins=["*"]` by default, allowing any website to make requests to this API.
- Files: `src/facecraft/core/config.py` (line 55), `src/facecraft/main.py` (lines 80-87)
- Current mitigation: Configurable via `FACECRAFT_CORS_ORIGINS` env var. Default allows all origins.
- Recommendations: Change default to restrict origins. Require explicit `FACECRAFT_CORS_ORIGINS` in production. Document CORS security implications.

**API key defined but never enforced:**
- Risk: `FACECRAFT_API_KEY` setting exists but is never used in authentication middleware.
- Files: `src/facecraft/core/config.py` (line 56), but not referenced anywhere in routes
- Current mitigation: None - setting is loaded but ignored.
- Recommendations: Implement Bearer token authentication middleware that checks this key on protected endpoints.

**No rate limiting:**
- Risk: API endpoints have no rate limiting. Malicious clients could DOS the service.
- Files: All route handlers in `src/facecraft/api/routes/process.py`
- Current mitigation: Docker memory limits provide some protection.
- Recommendations: Add rate limiting middleware (e.g., slowapi) with per-IP or per-key limits.

**File cleanup doesn't verify ownership before deletion:**
- Risk: `/api/v1/jobs/{job_id}` endpoint allows any user to delete any job by UUID.
- Files: `src/facecraft/api/routes/process.py` (lines 245-263)
- Current mitigation: Job IDs are 8-char UUIDs (guessing resistant).
- Recommendations: In multi-tenant scenario, add user/session context to job tracking.

## Performance Bottlenecks

**Rembg session created per BackgroundRemover instance:**
- Problem: New rembg session allocated on every processor initialization.
- Files: `src/facecraft/processing/background.py` (line 21)
- Cause: No session reuse or pooling. Each session loads ONNX model into memory.
- Improvement path: Create session once at startup, share across processor instances. Could reduce initialization time by seconds.

**JPEG quality written multiple times in loop:**
- Problem: Adaptive JPEG compression writes file to disk in loop, testing size each time.
- Files: `src/facecraft/processing/processor.py` (lines 234-241)
- Cause: Binary search for quality level implemented with disk I/O per iteration.
- Improvement path: Estimate quality from image entropy in memory first. Max 3 disk writes instead of potentially 13.

**No request batching in batch endpoint:**
- Problem: Batch processing (`/api/v1/process/batch`) processes files sequentially despite name.
- Files: `src/facecraft/api/routes/process.py` (lines 301-336)
- Cause: Simple for loop over files, no parallel processing.
- Improvement path: Use asyncio.gather() or ProcessPoolExecutor to process 4-8 images in parallel (respects `max_concurrent_jobs` setting).

**Models loaded synchronously on every request:**
- Problem: PhotoProcessor creates new instances of heavy models (CodeFormer, dlib, rembg) on first request if not initialized.
- Files: `src/facecraft/api/dependencies.py` (lines 36-41)
- Cause: Lazy initialization could happen during request handling.
- Improvement path: Pre-initialize in lifespan startup, make it blocking event.

## Fragile Areas

**Face alignment after background removal:**
- Files: `src/facecraft/processing/processor.py` (lines 140-149)
- Why fragile: Rotation can cause black borders in transparent image. Re-detection after rotation may fail if face moves off-image.
- Safe modification: Test with rotated portrait images. Validate face still detected after alignment before proceeding.
- Test coverage: No tests for alignment edge cases (rotated faces, extreme angles).

**CodeFormer model dependency on facexlib**:
- Files: `src/facecraft/processing/face_enhancement.py` (lines 41-67)
- Why fragile: Hard import of `facexlib.utils.face_restoration_helper` inside try-except. If facexlib API changes, code silently fails with warning.
- Safe modification: Test with different facexlib versions. Consider version pinning or feature detection.
- Test coverage: No tests for CodeFormer initialization or enhancement pipeline.

**JPEG compression quality heuristic:**
- Files: `src/facecraft/processing/processor.py` (lines 233-243)
- Why fragile: Loop assumes quality decreases file size monotonically. Some images may not reach target size at any quality.
- Safe modification: Add safety check: if quality reaches 50 and still oversized, raise error rather than returning oversized JPEG.
- Test coverage: No tests for edge cases (extremely complex images, pathological compression).

**Alpha channel handling inconsistent:**
- Files: `src/facecraft/processing/` (multiple files deal with BGRA/BGR conversion)
- Why fragile: Different modules assume different channel formats. OvalMask expects BGRA, PhotoEnhancer handles both.
- Safe modification: Add explicit dtype/channel validation at module boundaries. Use type hints: `np.ndarray[..., np.uint8]` doesn't exist in numpy but document expected shape.
- Test coverage: No tests for channel conversion edge cases.

## Scaling Limits

**Single PhotoProcessor instance shared across all requests:**
- Current capacity: `max_concurrent_jobs=4` setting defines logical limit but enforced nowhere in code.
- Limit: Torch models are not thread-safe. Concurrent requests to same CodeFormer instance cause race conditions.
- Scaling path: Implement request queue with semaphore that limits concurrent processing. Or pool multiple processor instances.

**Models loaded in GPU memory:**
- Current capacity: GPU models use ~8-12GB VRAM. Default device auto-selects CUDA if available.
- Limit: Docker GPU deployment limited by NVIDIA GPU memory. Batch size cannot increase.
- Scaling path: Use model quantization (INT8) to reduce memory. Implement model offloading (keep on CPU, swap to GPU per request).

**Disk I/O for every processed image:**
- Current capacity: Each job writes PNG + JPG to disk. Old files cleaned up after 24 hours.
- Limit: Long-running server accumulates output files. Heavy disk I/O under load.
- Scaling path: Implement optional in-memory mode returning base64 directly. Add S3/cloud storage backend option.

**Single rembg session not thread-safe:**
- Current capacity: BackgroundRemover creates one session per processor, but rembg session itself is not thread-safe.
- Limit: Concurrent requests to `remove_background()` may cause ONNX runtime errors.
- Scaling path: Thread-safe session pool or per-request session creation. Add mutex around rembg operations.

## Dependencies at Risk

**torch and torchvision version pinned to 2.0.1:**
- Risk: Pinned versions may have security vulnerabilities or compatibility issues with newer CUDA.
- Files: `requirements.txt` (lines 23-24)
- Impact: Cannot easily update to newer stable versions. GPU support fixed to CUDA 11.8.
- Migration plan: Create separate requirements files for major PyTorch versions. Use >=2.0.0,<3.0.0 constraint instead.

**dlib dependency with no fallback:**
- Risk: dlib requires compilation. If build fails on new systems, face detection unavailable.
- Files: `src/facecraft/processing/face_detection.py` imports dlib unconditionally
- Impact: Shape predictor optional but face detector not. Could use RetinaFace as fallback.
- Migration plan: Abstract face detection interface. Implement RetinaFace backend as fallback if dlib unavailable.

**rembg model hardcoded to u2net_human_seg:**
- Risk: Model is frozen in time. If rembg updates default model, this stays outdated.
- Files: `src/facecraft/processing/background.py` (line 13, 21)
- Impact: May miss improvements in background removal. No fallback if model becomes unavailable.
- Migration plan: Make model name configurable. Document which rembg version tested with.

**basicsr and facexlib versions not strictly constrained:**
- Risk: facexlib version 0.3.0+ could have API changes. basicsr version could diverge.
- Files: `pyproject.toml` (lines 55-56)
- Impact: Face enhancement could silently fail if dependencies break.
- Migration plan: Pin facexlib==0.3.0 and basicsr==1.4.2 exactly, or run compatibility matrix tests.

## Missing Critical Features

**No input/output validation schema:**
- Problem: `/api/v1/process` endpoint has 11 separate Form parameters. No single request schema.
- Blocks: Cannot easily validate request schema for API documentation or testing.
- Workaround: Routes use individual Form() parameters instead of single Pydantic model. Hard to version API.
- Solution: Unify to use ProcessingOptionsRequest schema like requests.py defines.

**No async processing:**
- Problem: Image processing is CPU-intensive and blocks event loop.
- Blocks: Cannot handle concurrent requests efficiently. Each worker blocked during processing.
- Workaround: Increase uvicorn workers (config default: 1). Causes memory overhead (each worker loads all models).
- Solution: Use ProcessPoolExecutor to offload processing to worker threads/processes.

**No request cancellation:**
- Problem: No way to cancel long-running image processing after upload.
- Blocks: Users cannot abort if file is stuck processing.
- Workaround: None - must wait for timeout or server restart.
- Solution: Implement request timeout + background task cancellation.

**No image format conversion:**
- Problem: Only accepts JPEG/PNG input. No WEBP, GIF, TIFF support.
- Blocks: Users with other formats must convert before upload.
- Workaround: Use external tools to convert format first.
- Solution: Use Pillow to auto-convert any image format to RGB before processing.

## Test Coverage Gaps

**No unit tests for processing pipeline:**
- What's not tested: Face detection edge cases (no face, multiple faces, extreme angles), alignment rotation effects, background removal on different image types.
- Files: Entire `src/facecraft/processing/` module
- Risk: Regressions in core functionality go undetected. Changes to processor.py could break image pipeline silently.
- Priority: High - core business logic

**No tests for API endpoint validation:**
- What's not tested: Form parameter validation (negative widths, invalid RGB values >255), file upload limits, batch endpoint behavior with 0 or 100 files.
- Files: `src/facecraft/api/routes/process.py`
- Risk: Invalid requests could crash server or produce corrupt output.
- Priority: High - security and stability

**No integration tests with real models:**
- What's not tested: End-to-end processing with actual dlib/CodeFormer models. Only testing imports/initialization.
- Files: `tests/` directory (empty or missing)
- Risk: Model API changes undetected until production.
- Priority: Medium - caught by manual testing but should be automated

**No tests for concurrent request handling:**
- What's not tested: Multiple requests processed simultaneously. Race conditions in global state `_processing_times`.
- Files: `src/facecraft/api/dependencies.py`
- Risk: Concurrency bugs only appear under load.
- Priority: Medium - important for production scaling

**No tests for error cases:**
- What's not tested: Corrupted image files, missing models at startup, disk full during output writing, network timeout during base64 reading.
- Files: `src/facecraft/api/routes/process.py`, `src/facecraft/processing/processor.py`
- Risk: Error handling code is untested. HTTPException messages may expose internal paths or sensitive info.
- Priority: Medium - production resilience

---

*Concerns audit: 2026-02-18*
