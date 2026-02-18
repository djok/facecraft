# Testing Patterns

**Analysis Date:** 2026-02-18

## Test Framework

**Runner:**
- `pytest` >= 7.0.0 - Primary test framework
- Config: `pyproject.toml` with `[tool.pytest.ini_options]`
- `testpaths = ["tests"]` - Tests located in `tests/` directory at project root
- `asyncio_mode = "auto"` - Automatic async test handling

**Assertion Library:**
- `pytest` built-in assertions and fixtures

**Run Commands:**
```bash
pytest                        # Run all tests
pytest -v                     # Verbose output
pytest tests/                 # Run specific directory
pytest -k test_name           # Run by name pattern
pytest --cov                  # Generate coverage report (requires pytest-cov)
pytest --cov-report=html      # HTML coverage report
```

**Additional Test Dependencies (from `pyproject.toml`):**
- `pytest-cov>=4.0.0` - Coverage measurement
- `pytest-asyncio>=0.21.0` - Async test support (paired with `asyncio_mode = "auto"`)
- `httpx>=0.24.0` - Async HTTP client for testing API endpoints

## Test File Organization

**Location:**
- Tests colocated in separate `tests/` directory at project root (not alongside source)
- Mirrors source structure: `tests/api/`, `tests/processing/`, `tests/core/`

**Naming:**
- Test files: `test_*.py` or `*_test.py` convention expected (pytest discovery)
- Test functions: `test_*` prefix required
- Test classes (if used): `Test*` prefix

**Structure:**
```
tests/
├── api/
│   ├── test_process_endpoints.py
│   ├── test_health_endpoints.py
│   └── test_dependencies.py
├── processing/
│   ├── test_processor.py
│   ├── test_face_detection.py
│   ├── test_background_removal.py
│   ├── test_face_enhancement.py
│   └── test_photo_enhancement.py
├── core/
│   ├── test_config.py
│   └── test_exceptions.py
└── conftest.py              # Shared fixtures and configuration
```

**Current Status:**
No test files currently exist in the codebase. Full test suite needs to be created.

## Test Structure

**Suite Organization:**
Standard pytest structure expected:
```python
import pytest
from facecraft.api.routes.process import router
from facecraft.processing.processor import PhotoProcessor, ProcessingOptions

class TestPhotoProcessor:
    """Test suite for PhotoProcessor class."""

    @pytest.fixture
    def processor(self):
        """Create processor instance for testing."""
        return PhotoProcessor()

    def test_process_image_success(self, processor, sample_image):
        """Test successful image processing."""
        options = ProcessingOptions(width=648, height=648)
        result = processor.process_image(sample_image, "/tmp/output.png", options)
        assert result.success is True
        assert result.face_detected is True
```

**Patterns to Implement:**
- Class-based test organization for grouped related tests (e.g., `TestPhotoProcessor`, `TestFaceDetector`, `TestProcessEndpoints`)
- Fixtures for reusable test data and dependencies (see Fixtures section)
- Parametrized tests for multiple input cases: `@pytest.mark.parametrize("width,height", [(648, 648), (512, 512)])`
- Async test support with `@pytest.mark.asyncio` for endpoint tests

## Mocking

**Framework:** `unittest.mock` (Python standard library)

**Patterns to Implement:**

Mocking external dependencies (models, file I/O):
```python
from unittest.mock import Mock, patch, MagicMock

def test_processor_handles_missing_face(processor):
    """Test handling when no face detected."""
    with patch.object(processor.face_detector, 'detect_face', return_value=None):
        result = processor.process_image("test.jpg", "/tmp/out.png")
        assert result.success is False
        assert result.error == "no_face_detected"
```

Mocking FastAPI dependencies:
```python
@pytest.fixture
def mock_processor():
    """Mock PhotoProcessor for endpoint testing."""
    processor = Mock(spec=PhotoProcessor)
    processor.process_image.return_value = ProcessingResult(
        success=True,
        face_detected=True
    )
    return processor

async def test_process_endpoint(client, mock_processor):
    """Test /process endpoint."""
    with patch('facecraft.api.dependencies.get_processor', return_value=mock_processor):
        response = client.post("/api/v1/process", files={"file": ("test.jpg", b"fake")})
        assert response.status_code == 200
```

**What to Mock:**
- External ML models (dlib, CodeFormer) - expensive to load in tests
- File system operations for isolation
- Temporary directories and file cleanup
- External dependencies that are slow or flaky (model loading)

**What NOT to Mock:**
- Core business logic (face detection, background removal algorithms) - test the real behavior
- Pydantic validation and model conversion
- Configuration and settings (use fixtures or temporary configs)
- FastAPI dependency injection structure (it handles dependencies correctly)

## Fixtures and Factories

**Test Data:**

Sample image fixture:
```python
@pytest.fixture
def sample_image():
    """Create a minimal valid test image."""
    import numpy as np
    import cv2
    # Create 648x648 BGR image
    img = np.random.randint(0, 256, (648, 648, 3), dtype=np.uint8)
    temp_path = "/tmp/test_image.jpg"
    cv2.imwrite(temp_path, img)
    yield temp_path
    os.unlink(temp_path)
```

Processing options factory:
```python
@pytest.fixture
def processing_options():
    """Default ProcessingOptions for testing."""
    return ProcessingOptions(
        width=648,
        height=648,
        background_color=(240, 240, 240),
        face_margin=0.3,
        use_oval_mask=True,
        enhance_face=False,  # Disable for speed in tests
        enhance_fidelity=0.7,
        enhance_photo=True,
        max_jpeg_size_kb=99
    )
```

FastAPI test client:
```python
@pytest.fixture
def client():
    """Create FastAPI test client."""
    from fastapi.testclient import TestClient
    from facecraft.main import app
    return TestClient(app)
```

**Location:**
- Shared fixtures in `tests/conftest.py` at project root
- Module-specific fixtures in local `conftest.py` files (e.g., `tests/api/conftest.py` for API fixtures)
- Factory functions for creating test data (parametrized configurations)

## Coverage

**Requirements:** Not explicitly enforced

**View Coverage:**
```bash
pytest --cov=facecraft --cov-report=html
# View in browser: htmlcov/index.html
```

**Target:** Recommended minimum 80% for API endpoints, 70% for processing modules (complex ML code may be hard to test comprehensively)

## Test Types

**Unit Tests:**
- Scope: Individual functions and methods (e.g., `test_detect_face()`, `test_remove_background()`)
- Approach: Test with isolated inputs, mock external dependencies
- Location: `tests/processing/`, `tests/core/`
- Example: Testing `FaceDetector.detect_face()` with different image sizes and quality

**Integration Tests:**
- Scope: Multiple components working together (e.g., full processing pipeline, endpoint with dependencies)
- Approach: Use real components where possible, mock only external services
- Location: `tests/api/` for endpoint integration, `tests/processing/` for processor pipeline
- Example: Testing `PhotoProcessor.process_image()` end-to-end without real ML models

**E2E Tests:**
- Framework: Not currently in use
- Approach if added: Could use `pytest` with real image files and verify full workflows
- Scope: Would test actual API endpoints with realistic requests

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_async_endpoint(client):
    """Test async endpoint with pytest-asyncio."""
    response = await client.get("/health")
    assert response.status_code == 200

# Or with test client (TestClient handles async):
def test_async_endpoint_with_testclient(client):
    response = client.get("/health")
    assert response.status_code == 200
```

**Error Testing:**
```python
def test_process_handles_no_face(processor):
    """Test error when no face detected."""
    result = processor.process_image("no_face.jpg", "/tmp/out.png")
    assert result.success is False
    assert result.error == "no_face_detected"
    assert result.face_detected is False

def test_endpoint_invalid_format(client):
    """Test endpoint rejects invalid file formats."""
    with open("/tmp/test.txt", "w") as f:
        f.write("not an image")

    with open("/tmp/test.txt", "rb") as f:
        response = client.post(
            "/api/v1/process",
            files={"file": ("test.txt", f)}
        )
    assert response.status_code == 400
    assert "Invalid format" in response.json()["detail"]
```

**Parametrized Tests:**
```python
@pytest.mark.parametrize("width,height,margin", [
    (648, 648, 0.3),
    (512, 512, 0.2),
    (1024, 1024, 0.4),
])
def test_process_various_dimensions(processor, width, height, margin):
    """Test processing with different dimensions."""
    options = ProcessingOptions(
        width=width,
        height=height,
        face_margin=margin
    )
    result = processor.process_image("test.jpg", "/tmp/out.png", options)
    assert result.success is True
    assert result.face_detected is True
```

## Test Execution Strategy

**Model Loading Optimization:**
- Models are expensive to load (GB+); disable in tests with `enhance_face=False` in fixture
- Mock `CodeFormer` initialization for most tests
- Create integration test subset that tests with real models (run separately)

**File Handling:**
- Use `tempfile.TemporaryDirectory()` for output directories
- Ensure cleanup in fixtures with `yield` and cleanup code
- Never commit test images; generate minimal synthetic images instead

**Performance:**
- Keep unit tests <100ms per test
- Use mocking to avoid model loading in most tests
- Parametrize to test multiple cases without duplicating setup

## Configuration for Testing

**pytest.ini equivalent (in pyproject.toml):**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**Test Requirements (from pyproject.toml):**
```
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-asyncio>=0.21.0
httpx>=0.24.0
```

---

*Testing analysis: 2026-02-18*
