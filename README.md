# Facecraft

AI-powered portrait processing API with background removal, face detection, alignment, and enhancement.

## Features

- **Background Removal** - AI-powered with u2net_human_seg model
- **Face Detection** - Accurate detection using dlib
- **Face Alignment** - Automatic alignment based on eye positions
- **Face Enhancement** - Quality restoration with CodeFormer
- **Photo Enhancement** - Auto exposure, white balance, sharpening
- **Oval Mask** - Professional portrait masks with feathering
- **Adaptive Compression** - Smart JPEG compression for size limits

## Quick Start

### Docker (Recommended)

**CPU Version:**
```bash
docker build -f docker/Dockerfile.cpu -t facecraft:cpu .
docker run -p 8000:8000 facecraft:cpu
```

**GPU Version (requires nvidia-docker):**
```bash
docker build -f docker/Dockerfile.gpu -t facecraft:gpu .
docker run --gpus all -p 8000:8000 facecraft:gpu
```

### Test the API

```bash
# Health check
curl http://localhost:8000/health

# Process an image
curl -X POST http://localhost:8000/api/v1/process \
  -F "file=@photo.jpg" \
  -o result.json

# Quick processing (returns image directly)
curl -X POST http://localhost:8000/api/v1/process/quick \
  -F "file=@photo.jpg" \
  -o processed.png
```

## API Documentation

Interactive documentation available at:
- **Swagger UI**: http://localhost:8000/docs
- **OpenAPI spec**: http://localhost:8000/openapi.json

## API Endpoints

### Health & Status

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Basic health check (liveness probe) |
| `/ready` | GET | Readiness check (models loaded) |
| `/status` | GET | Detailed status with device info and statistics |

### Processing

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/process` | POST | Process single image with full options |
| `/api/v1/process/quick` | POST | Quick processing, returns image directly |
| `/api/v1/process/batch` | POST | Process multiple images |
| `/api/v1/download/{job_id}/{format}` | GET | Download processed image (png/jpg) |
| `/api/v1/jobs/{job_id}` | DELETE | Delete job files |

## Usage Examples

### Python

```python
import requests

# Basic processing
with open("photo.jpg", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/v1/process",
        files={"file": f}
    )

result = response.json()
print(f"Job ID: {result['job_id']}")

# Download result
if result["success"]:
    png_response = requests.get(f"http://localhost:8000{result['png_url']}")
    with open("processed.png", "wb") as f:
        f.write(png_response.content)
```

### cURL

```bash
# With custom options
curl -X POST http://localhost:8000/api/v1/process \
  -F "file=@photo.jpg" \
  -F "width=400" \
  -F "height=400" \
  -F "background_r=255" \
  -F "background_g=255" \
  -F "background_b=255" \
  -F "face_margin=0.4"
```

### JavaScript

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const response = await fetch('http://localhost:8000/api/v1/process', {
    method: 'POST',
    body: formData
});

const result = await response.json();
if (result.success) {
    window.location.href = `http://localhost:8000${result.png_url}`;
}
```

## Configuration

All settings can be configured via environment variables with the `FACECRAFT_` prefix.

| Variable | Default | Description |
|----------|---------|-------------|
| `FACECRAFT_HOST` | 0.0.0.0 | Server host |
| `FACECRAFT_PORT` | 8000 | Server port |
| `FACECRAFT_DEVICE` | auto | Device: auto, cpu, cuda |
| `FACECRAFT_DEFAULT_WIDTH` | 648 | Default output width |
| `FACECRAFT_DEFAULT_HEIGHT` | 648 | Default output height |
| `FACECRAFT_DEFAULT_FACE_MARGIN` | 0.3 | Margin around face |
| `FACECRAFT_DEFAULT_OVAL_MASK` | true | Apply oval mask |
| `FACECRAFT_CLEANUP_AGE_HOURS` | 24 | Auto-cleanup old files |

See [.env.example](.env.example) for all available options.

## Docker Images

| Image | Base | Size | Use Case |
|-------|------|------|----------|
| `facecraft:cpu` | python:3.11-slim | ~16.6 GB | Standard deployment |
| `facecraft:gpu` | nvidia/cuda:12.1 | ~23.5 GB | CUDA acceleration |

All models are bundled in the image - no downloads on startup.

## Performance Benchmarks

### Test Hardware

| Component | Specification |
|-----------|---------------|
| **CPU** | AMD Ryzen 9 7900 12-Core (24 threads) @ 5.4 GHz |
| **RAM** | 32 GB DDR5 |
| **GPU** | NVIDIA GeForce RTX 4090 (24 GB VRAM) |
| **OS** | Linux (WSL2 on Windows) |

### Processing Time Comparison

| Version | Avg. Time/Image | Speedup |
|---------|-----------------|---------|
| **CPU** | ~1.45 seconds | 1x (baseline) |
| **GPU** | ~0.43 seconds | **3.4x faster** |

*Benchmark: 5 portrait images, 648x648 output, background removal + face detection + alignment.*

### Detailed Results

**CPU Version (facecraft:cpu)**
```
Test 1: 1.52s
Test 2: 1.41s
Test 3: 1.43s
Test 4: 1.46s
Test 5: 1.44s
Average: 1.45s
```

**GPU Version (facecraft:gpu)**
```
Test 1: 0.50s (includes warmup)
Test 2: 0.42s
Test 3: 0.41s
Test 4: 0.45s
Test 5: 0.40s
Average: 0.43s
```

### Recommendations

- **Development/Low volume**: CPU version is sufficient
- **Production/High volume**: GPU version recommended (3x+ faster)
- **Batch processing**: GPU version with parallel requests

## Models Included

- **dlib shape_predictor_68_face_landmarks.dat** (~95MB) - Face landmark detection
- **CodeFormer codeformer.pth** (~350MB) - Face quality enhancement
- **u2net_human_seg** (~170MB) - Background removal

## Development

### Local Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Download models manually
# See docker/Dockerfile.cpu for model URLs

# Run server
python -m uvicorn facecraft.main:app --reload
```

### Running Tests

```bash
pip install -r requirements.txt -e ".[dev]"
pytest tests/ -v
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [CodeFormer](https://github.com/sczhou/CodeFormer) - Face restoration
- [rembg](https://github.com/danielgatis/rembg) - Background removal
- [dlib](http://dlib.net/) - Face detection
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
