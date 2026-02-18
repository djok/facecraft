# Technology Stack

**Analysis Date:** 2026-02-18

## Languages

**Primary:**
- Python 3.10+ - All application code and ML processing

## Runtime

**Environment:**
- Python 3.11 (primary) - Specified in `pyproject.toml` and Docker images
- Python 3.10 minimum supported version

**Package Manager:**
- pip - Standard Python package manager
- Lockfile: `requirements.txt` and `requirements-gpu.txt` (pinned versions)

## Frameworks

**Core:**
- FastAPI 0.109.0+ - Web API framework for REST endpoints at `src/facecraft/main.py`
- Uvicorn 0.27.0+ - ASGI server for running the application

**Configuration:**
- Pydantic 2.5.0+ - Data validation and settings at `src/facecraft/core/config.py`
- Pydantic Settings 2.1.0+ - Environment variable management

**Processing & ML:**
- OpenCV (opencv-python) 4.8.0+ - Image processing operations
- NumPy 1.24.0 (< 2.0) - Numerical computations
- Pillow 10.0.0+ - Image manipulation and format handling
- PyTorch 2.0.1 - Deep learning framework with CPU/GPU variants
- Torchvision 0.15.2 - Vision models and transforms

**Face Processing:**
- dlib 19.24.0+ - Face detection and landmark detection at `src/facecraft/processing/face_detection.py`
- rembg 2.0.50+ - Background removal using u2net_human_seg model at `src/facecraft/processing/background.py`
- basicsr 1.4.2 - BasicSR framework for face restoration
- facexlib 0.3.0+ - Face utilities for CodeFormer integration
- realesrgan 0.3.0+ - Real-ESRGAN upsampling
- CodeFormer - Face quality enhancement model (downloaded at build time)

**Utilities:**
- ONNX Runtime 1.15.0+ - For rembg background removal acceleration
- Kornia 0.7.0+ - Computer vision operations (PyTorch-based)
- einops 0.7.0+ - Tensor manipulation utilities
- LPIPS 0.1.4+ - Perceptual loss for quality metrics

**File Handling:**
- python-multipart 0.0.6+ - Multipart form data parsing for file uploads

## Key Dependencies

**Critical (Core Processing):**
- rembg[cpu] - Background removal pipeline at `src/facecraft/processing/background.py`
- PyTorch/Torchvision - Face detection and enhancement backend
- dlib - Accurate face landmark detection (95MB model)
- CodeFormer - State-of-the-art face restoration model (350MB)

**Infrastructure:**
- FastAPI - RESTful API server with automatic OpenAPI documentation
- Uvicorn[standard] - ASGI server with standard extra dependencies

## Configuration

**Environment:**
- `.env` file support with `FACECRAFT_` prefix for all settings
- Environment variables define behavior at runtime (see `.env.example`)
- Settings cached using `@lru_cache()` in `src/facecraft/core/config.py`

**Key Configuration Parameters:**
- `FACECRAFT_DEVICE` - auto/cpu/cuda device selection
- `FACECRAFT_MODELS_DIR` - Path to pre-downloaded models (default: `/app/models`)
- `FACECRAFT_UPLOAD_DIR` - Temporary upload directory
- `FACECRAFT_OUTPUT_DIR` - Processed output directory
- `FACECRAFT_MAX_UPLOAD_SIZE_MB` - File size limit (default: 20MB)
- `FACECRAFT_CLEANUP_AGE_HOURS` - Auto-cleanup old files (default: 24h)
- Processing defaults: width, height, background color, face margin, enhancement settings

**Build Configuration:**
- `pyproject.toml` - Project metadata and dependencies
- Ruff configuration: line-length=100, target-version=py311
- Black configuration: line-length=100
- MyPy configuration for type checking

## Platform Requirements

**Development:**
- Python 3.10+
- CMake and build-essential for compiling dlib
- libopenblas and liblapack for numerical libraries
- Model files must be pre-downloaded (~615MB total)

**Production - CPU:**
- Base: `python:3.11-slim` image
- Runtime dependencies: libopenblas0, liblapack3, libgl1, libglib2.0-0, libsm6, libxext6, libxrender1
- Image size: ~16.6 GB (including bundled models)
- Device: Auto-detection or explicit CPU configuration via `FACECRAFT_DEVICE=cpu`

**Production - GPU:**
- Base: `nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04` image
- CUDA 12.1 runtime with cuDNN 8
- PyTorch compiled with CUDA 11.8 support (`torch==2.0.1+cu118`)
- onnxruntime-gpu for GPU-accelerated background removal
- Image size: ~23.5 GB (including CUDA runtime and bundled models)
- Requires NVIDIA Docker and GPU hardware
- Device: Auto-detection or explicit CUDA configuration via `FACECRAFT_DEVICE=cuda`

---

*Stack analysis: 2026-02-18*
