# Facecraft

AI-powered portrait processing API with background removal, face detection, alignment, and enhancement.

## Quick Start

Pull and run from Docker Hub:

```bash
docker run -p 8000:8000 djok/facecraft:cpu
```

GPU version (requires NVIDIA Container Toolkit):

```bash
docker run --gpus all -p 8000:8000 djok/facecraft:gpu
```

Verify it is running:

```bash
curl http://localhost:8000/health
```

Process a portrait:

```bash
curl -X POST http://localhost:8000/api/v1/process/quick \
  -F "file=@photo.jpg" -o processed.png
```

Interactive API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

## Performance

| Version | Image | Avg. Time/Image | Speedup |
|---------|-------|-----------------|---------|
| CPU | `djok/facecraft:cpu` | ~1.45s | 1x (baseline) |
| GPU | `djok/facecraft:gpu` | ~0.43s | **3.4x faster** |

*Tested on: AMD Ryzen 9 7900 12-Core (24 threads) @ 5.4 GHz, 32 GB DDR5, NVIDIA RTX 4090 (24 GB VRAM), Linux (WSL2). 5 portrait images, 648x648 output, background removal + face detection + alignment.*

### Detailed Results

**CPU Version (`djok/facecraft:cpu`)**

```text
Test 1: 1.52s
Test 2: 1.41s
Test 3: 1.43s
Test 4: 1.46s
Test 5: 1.44s
Average: 1.45s
```

**GPU Version (`djok/facecraft:gpu`)**

```text
Test 1: 0.50s (includes warmup)
Test 2: 0.42s
Test 3: 0.41s
Test 4: 0.45s
Test 5: 0.40s
Average: 0.43s
```

### Recommendations

- **Development / low volume**: CPU version is sufficient
- **Production / high volume**: GPU version recommended (3x+ faster)
- **Batch processing**: GPU version with parallel requests

## API Endpoints

### Health and Status

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Basic health check (liveness probe) |
| GET | `/ready` | Readiness check (models loaded) |
| GET | `/status` | Detailed status with device info and statistics |

### Processing

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/process` | Process single image with full options |
| POST | `/api/v1/process/quick` | Quick processing, returns PNG directly |
| POST | `/api/v1/process/batch` | Process multiple images |
| GET | `/api/v1/download/{job_id}/{format}` | Download processed image (`png` or `jpg`) |
| DELETE | `/api/v1/jobs/{job_id}` | Delete job files |

### Examples

Health check:

```bash
curl http://localhost:8000/health
```

Quick processing (returns PNG directly):

```bash
curl -X POST http://localhost:8000/api/v1/process/quick \
  -F "file=@photo.jpg" -o processed.png
```

Full processing with custom options:

```bash
curl -X POST http://localhost:8000/api/v1/process \
  -F "file=@photo.jpg" \
  -F "width=400" \
  -F "height=400" \
  -F "background_r=255" \
  -F "background_g=255" \
  -F "background_b=255" \
  -F "face_margin=0.4"
```

Batch processing:

```bash
curl -X POST http://localhost:8000/api/v1/process/batch \
  -F "files=@photo1.jpg" \
  -F "files=@photo2.jpg" \
  -F "files=@photo3.jpg"
```

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

## Environment Variables

All settings use the `FACECRAFT_` prefix and can be passed via `-e` flags or an env file.

### Server

| Variable | Default | Description |
|----------|---------|-------------|
| `FACECRAFT_HOST` | `0.0.0.0` | Server bind address |
| `FACECRAFT_PORT` | `8000` | Server port |
| `FACECRAFT_WORKERS` | `1` | Number of Uvicorn workers |
| `FACECRAFT_DEBUG` | `false` | Enable debug mode (hot reload) |
| `FACECRAFT_LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### Device

| Variable | Default | Description |
|----------|---------|-------------|
| `FACECRAFT_DEVICE` | `auto` | Compute device: `auto`, `cpu`, `cuda`, `cuda:0` |

### Model Paths

| Variable | Default | Description |
|----------|---------|-------------|
| `FACECRAFT_MODELS_DIR` | `/app/models` | Path to model files directory |
| `FACECRAFT_PREDICTOR_PATH` | (auto) | Override path to dlib shape predictor |
| `FACECRAFT_CODEFORMER_PATH` | (auto) | Override path to CodeFormer model |

### Processing Defaults

| Variable | Default | Description |
|----------|---------|-------------|
| `FACECRAFT_DEFAULT_WIDTH` | `648` | Default output image width |
| `FACECRAFT_DEFAULT_HEIGHT` | `648` | Default output image height |
| `FACECRAFT_DEFAULT_BACKGROUND_R` | `240` | Default background red channel (0-255) |
| `FACECRAFT_DEFAULT_BACKGROUND_G` | `240` | Default background green channel (0-255) |
| `FACECRAFT_DEFAULT_BACKGROUND_B` | `240` | Default background blue channel (0-255) |
| `FACECRAFT_DEFAULT_FACE_MARGIN` | `0.3` | Margin around detected face (0.0-1.0) |
| `FACECRAFT_DEFAULT_OVAL_MASK` | `true` | Apply oval mask by default |
| `FACECRAFT_DEFAULT_ENHANCE_FIDELITY` | `0.7` | CodeFormer fidelity weight (0.0-1.0) |

### Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `FACECRAFT_UPLOAD_DIR` | `/app/uploads` | Directory for uploaded files |
| `FACECRAFT_OUTPUT_DIR` | `/app/processed` | Directory for processed output |
| `FACECRAFT_MAX_UPLOAD_SIZE_MB` | `20` | Maximum upload file size in MB |
| `FACECRAFT_CLEANUP_AGE_HOURS` | `24` | Auto-delete files older than N hours |

### Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `FACECRAFT_MAX_CONCURRENT_JOBS` | `4` | Maximum parallel processing jobs |
| `FACECRAFT_BATCH_MAX_FILES` | `50` | Maximum files per batch request |

### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `FACECRAFT_CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |
| `FACECRAFT_API_KEY` | (none) | Optional API key for authentication |

## Bundled Models

| Model | File | Size | Purpose |
|-------|------|------|---------|
| dlib shape predictor | `shape_predictor_68_face_landmarks.dat` | ~95 MB | Face landmark detection (68 points) |
| CodeFormer | `codeformer.pth` | ~350 MB | AI face quality enhancement |
| u2net | `u2net_human_seg.onnx` | ~170 MB | Background removal segmentation |

All models are bundled in the Docker image. No downloads on first run.

## Image Sizes

| Tag | Uncompressed | Contents |
|-----|-------------|----------|
| `djok/facecraft:cpu` | 4.08 GB | PyTorch 2.0.1 CPU (~1.8 GB) + models (~615 MB) + runtime |
| `djok/facecraft:gpu` | 13.8 GB | CUDA 12.1 runtime + PyTorch+CUDA (~5.9 GB) + models (~615 MB) |

All models are bundled -- no internet access required at runtime. Compressed sizes on Docker Hub will be smaller than the uncompressed values above.

## Volumes and Data Persistence

Mount named volumes to persist uploaded and processed files across container restarts:

```bash
docker run -p 8000:8000 \
  -v facecraft-uploads:/app/uploads \
  -v facecraft-output:/app/processed \
  djok/facecraft:cpu
```

Bind mount a local directory for direct file access:

```bash
docker run -p 8000:8000 \
  -v ./my-uploads:/app/uploads \
  -v ./my-output:/app/processed \
  djok/facecraft:cpu
```

The `docker-compose.yml` in this repository already configures named volumes (`uploads` and `processed`) for both services.

## Docker Compose

Run with profiles:

```bash
docker compose --profile cpu up -d
docker compose --profile gpu up -d
```

Stop:

```bash
docker compose --profile cpu down
docker compose --profile gpu down
```

Both profiles share port 8000 -- run only one at a time.

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
