# Coding Conventions

**Analysis Date:** 2026-02-18

## Naming Patterns

**Files:**
- snake_case for all Python files: `processor.py`, `face_detection.py`, `face_enhancement.py`
- Descriptive names matching module purpose: `background.py`, `photo_enhancement.py`, `config.py`
- Schema files grouped by purpose: `requests.py`, `responses.py` in `api/schemas/`
- Route files by endpoint domain: `process.py`, `health.py` in `api/routes/`

**Functions:**
- snake_case with descriptive names: `detect_face()`, `remove_background()`, `get_predictor_path()`
- Async endpoints clearly named: `process_single_photo()`, `readiness_check()`, `download_processed_photo()`
- Private/internal functions prefixed with underscore: `_auto_exposure()`, `_auto_white_balance()`, `_init_codeformer()`, `_save_output()`
- Property accessors as `@property`: `has_face_alignment`, `has_face_enhancement`, `default_background_color`, `cors_origins_list`

**Variables:**
- snake_case throughout: `upload_dir`, `output_dir`, `processing_time`, `job_id`, `face_rect`, `max_age_hours`
- Descriptive naming for collections: `results`, `processing_times`, `faces`, `landmarks`
- Configuration values use clear names: `target_brightness`, `margin_w`, `margin_h`, `radius_x`, `radius_y`

**Types:**
- PascalCase for classes: `PhotoProcessor`, `BackgroundRemover`, `FaceDetector`, `FaceEnhancer`, `PhotoEnhancer`, `OvalMask`, `ImageResizer`
- Dataclasses: `ProcessingResult`, `ProcessingOptions`
- Exception classes: `FacecraftError`, `NoFaceDetectedError`, `ImageProcessingError`, `ModelLoadError`, `FileTooLargeError`
- Pydantic models: `HealthResponse`, `ReadyResponse`, `StatusResponse`, `ProcessResponse`, `BatchResponse`, `FacePosition`

## Code Style

**Formatting:**
- Tool: `black` with line-length = 100 (configured in `pyproject.toml`)
- Target version: Python 3.11
- All code is formatted to black standards

**Linting:**
- Tool: `ruff` with configuration in `pyproject.toml`
- Selected rules: `["E", "F", "W", "I", "N", "UP"]` (errors, undefined names, warnings, imports, naming, upgrades)
- Ignored: `["E501"]` (line length, handled by black instead)
- Target version: Python 3.11

**Type Checking:**
- Tool: `mypy` for static type analysis
- Configuration: `python_version = 3.11`, `warn_return_any = true`, `warn_unused_configs = true`
- Option: `ignore_missing_imports = true` for third-party libraries without stubs

## Import Organization

**Order:**
1. Standard library imports: `import os`, `import cv2`, `from pathlib import Path`, `from typing import Optional`
2. Third-party framework imports: `from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Depends`
3. Third-party library imports: `from pydantic import BaseModel, Field`, `from pydantic_settings import BaseSettings`, `import torch`, `import dlib`
4. Local application imports: `from facecraft.core.config import settings`, `from facecraft.processing.processor import PhotoProcessor`

**Path Aliases:**
- Imports use absolute paths from package root: `from facecraft.api.routes import health_router, process_router`
- No relative imports (no `from ..` or `.module` imports)
- Settings accessed via singleton: `from facecraft.core.config import settings`

**Example from `src/facecraft/api/routes/process.py`:**
```python
import time
import uuid
import shutil
import base64
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Depends
from fastapi.responses import FileResponse

from facecraft.api.schemas.requests import ProcessingOptionsRequest
from facecraft.api.schemas.responses import (
    ProcessResponse,
    ProcessResult,
    FacePosition,
    BatchResponse,
    BatchResultItem,
)
from facecraft.api.dependencies import get_processor, get_upload_dir, get_output_dir
from facecraft.processing.processor import PhotoProcessor
from facecraft.core.config import settings
```

## Error Handling

**Patterns:**
- Custom exception hierarchy: All exceptions inherit from `FacecraftError` base class in `src/facecraft/core/exceptions.py`
- Specific exceptions for distinct error cases: `NoFaceDetectedError`, `MultipleFacesDetectedError`, `ImageProcessingError`, `ModelLoadError`, `InvalidImageError`, `FileTooLargeError`
- HTTP endpoints raise `HTTPException` from FastAPI with descriptive status codes and messages
- Processing methods return result objects with success flag and error details rather than raising

**Example from `src/facecraft/api/routes/process.py` (lines 87-92):**
```python
try:
    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
```

**Example from `src/facecraft/processing/processor.py` (lines 121-128):**
```python
face_rect = self.face_detector.detect_face(image)
if face_rect is None:
    self.stats['no_face'] += 1
    return ProcessingResult(
        success=False,
        face_detected=False,
        error="no_face_detected"
    )
```

## Logging

**Framework:** `print()` for startup/shutdown messages, no formal logging framework configured

**Patterns:**
- Startup messages in application lifespan context manager (formatted with `=` separators): `src/facecraft/main.py` lines 22-43
- Warning messages for non-critical issues: `print(f"Warning: Could not load shape predictor: {e}")` in `src/facecraft/processing/face_detection.py` line 28
- No per-request logging; statistics tracked in-memory via `PhotoProcessor.stats` dict
- Performance timing: `time.time()` used to measure processing duration, stored in `ProcessingResult`

**Example from `src/facecraft/main.py`:**
```python
print("=" * 60)
print("Facecraft - AI Portrait Processing API")
print(f"Version: {__version__}")
print("=" * 60)
```

## Comments

**When to Comment:**
- Comments explain WHY, not WHAT (code should be self-documenting)
- Complex algorithms include step comments: `src/facecraft/processing/photo_enhancement.py` lines 75-103 explain exposure correction strategy
- Inline comments rare; used only for non-obvious logic (e.g., "More margin on top for forehead" in `face_detection.py` line 181)
- No redundant comments that repeat variable names or obvious code intent

**JSDoc/TSDoc:**
- All public methods have docstrings with Args, Returns, and description sections
- Module-level docstrings explain purpose: `"""Image processing endpoints."""`, `"""Face detection and alignment using dlib."""`
- Class docstrings explain role: `"""Main processor for portrait photo enhancement."""`
- Private methods may omit docstrings if purpose is clear from name and context

**Example from `src/facecraft/processing/processor.py` (lines 90-106):**
```python
def process_image(
    self,
    input_path: str,
    output_path: str,
    options: Optional[ProcessingOptions] = None
) -> ProcessingResult:
    """
    Process a single image through the full pipeline.

    Args:
        input_path: Path to input image
        output_path: Path for output image
        options: Processing options

    Returns:
        ProcessingResult with details about the processing
    """
```

## Function Design

**Size:**
- Functions average 10-50 lines
- Longer methods (>100 lines) like `process_image()` handle single logical workflow with clear steps
- Steps prefixed with comment numbers: `# 1. Load image`, `# 2. Face enhancement`, etc.

**Parameters:**
- Type hints on all parameters: `def process_image(self, input_path: str, output_path: str, options: Optional[ProcessingOptions] = None)`
- Optional parameters have sensible defaults (e.g., `options or ProcessingOptions()`)
- FastAPI endpoint parameters use Form/File/Depends dependency injection
- Maximum 5-7 parameters; complex configurations passed as dataclass objects

**Return Values:**
- Explicit return type hints: `-> ProcessingResult`, `-> list[dlib.rectangle]`, `-> Optional[dlib.rectangle]`
- Result objects used for complex returns: `ProcessingResult` dataclass with `success`, `error`, and detailed output fields
- Tuple returns for byte operations: `tuple[Optional[bytes], Optional[bytes], ProcessingResult]` from `process_image_bytes()`

## Module Design

**Exports:**
- Classes exported implicitly via module structure (no `__all__` declarations)
- Main imports from root: `from facecraft.api.routes import health_router, process_router`
- Dependencies managed via FastAPI's Depends() system in `src/facecraft/api/dependencies.py`

**Barrel Files:**
- Minimal use of barrel files
- `src/facecraft/api/routes/__init__.py` exports both routers: `from .health import router as health_router` and `from .process import router as process_router`
- Core modules import components individually rather than through barrel imports

**Example structure:**
- Configuration singleton: `from facecraft.core.config import settings` (with lru_cache wrapping)
- Dependency injection: `from facecraft.api.dependencies import get_processor, get_upload_dir, get_output_dir`
- Schema organization: Requests and responses in separate modules but same package

## Dataclass Conventions

**Format:**
- Dataclasses use `@dataclass` decorator for simple data holders
- `ProcessingOptions` provides configuration with defaults: `width: int = 648`, `height: int = 648`, `background_color: tuple[int, int, int] = (240, 240, 240)`
- `ProcessingResult` tracks operation outcomes with optional fields: `success: bool`, `error: Optional[str] = None`

**Example from `src/facecraft/processing/processor.py`:**
```python
@dataclass
class ProcessingOptions:
    """Options for photo processing."""
    width: int = 648
    height: int = 648
    background_color: tuple[int, int, int] = (240, 240, 240)
    face_margin: float = 0.3
    use_oval_mask: bool = True
    enhance_face: bool = True
    enhance_fidelity: float = 0.7
    enhance_photo: bool = True
    max_jpeg_size_kb: Optional[int] = 99
```

## Pydantic Configuration

**BaseModel Usage:**
- Request/response schemas inherit from `pydantic.BaseModel` in `src/facecraft/api/schemas/`
- Field validation with constraints: `Field(default=648, ge=64, le=4096)` for dimension bounds
- Optional fields for nullable values: `Optional[FacePosition] = None`

**Settings Configuration:**
- Application config uses `pydantic_settings.BaseSettings` in `src/facecraft/core/config.py`
- Environment variable mapping via aliases: `Field(default="0.0.0.0", alias="FACECRAFT_HOST")`
- Config includes: `env_file = ".env"`, `populate_by_name = True`, `extra = "ignore"`
- Properties for computed values: `default_background_color`, `cors_origins_list`, `get_device()`, `get_predictor_path()`

---

*Convention analysis: 2026-02-18*
