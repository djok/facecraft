"""Health and status endpoints."""

import time
import torch
from fastapi import APIRouter, Depends
from typing import Optional

from facecraft.api.schemas.responses import (
    HealthResponse,
    ReadyResponse,
    StatusResponse,
    DeviceInfo,
    ModelStatus,
    Statistics,
)
from facecraft.api.dependencies import get_processor, get_start_time, get_processing_stats
from facecraft.processing.processor import PhotoProcessor
from facecraft import __version__

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check for liveness probe.

    Returns a simple status indicating the service is running.
    """
    return HealthResponse(status="healthy")


@router.get("/ready", response_model=ReadyResponse)
async def readiness_check(processor: PhotoProcessor = Depends(get_processor)):
    """
    Readiness check for Kubernetes readiness probe.

    Checks if all required models are loaded and ready.
    """
    models_loaded = (
        processor.background_remover is not None and
        processor.face_detector is not None
    )

    return ReadyResponse(
        ready=models_loaded,
        models_loaded=models_loaded
    )


@router.get("/status", response_model=StatusResponse)
async def detailed_status(
    processor: PhotoProcessor = Depends(get_processor),
    start_time: float = Depends(get_start_time),
    stats: dict = Depends(get_processing_stats)
):
    """
    Detailed system status.

    Returns comprehensive information about:
    - Service version and uptime
    - Device (CPU/GPU) information
    - Model loading status
    - Processing statistics
    """
    # Device info
    device_type = "cuda" if torch.cuda.is_available() else "cpu"
    device_name = None
    cuda_version = None

    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        cuda_version = torch.version.cuda

    device = DeviceInfo(
        type=device_type,
        name=device_name,
        cuda_version=cuda_version
    )

    # Model status
    models = {
        "face_detector": ModelStatus(
            loaded=processor.face_detector is not None,
            type="dlib_frontal_face"
        ),
        "face_landmarks": ModelStatus(
            loaded=processor.has_face_alignment,
            type="shape_predictor_68"
        ),
        "face_enhancer": ModelStatus(
            loaded=processor.has_face_enhancement,
            type="codeformer"
        ),
        "background_remover": ModelStatus(
            loaded=processor.background_remover is not None,
            type="u2net_human_seg"
        )
    }

    # Statistics
    total = stats.get('total', 0)
    success_rate = stats.get('success_rate', 0.0)
    avg_time = stats.get('avg_processing_ms', 0.0)

    statistics = Statistics(
        total_processed=total,
        success_rate=success_rate,
        avg_processing_ms=avg_time
    )

    # Uptime
    uptime = int(time.time() - start_time)

    return StatusResponse(
        status="operational",
        version=__version__,
        uptime_seconds=uptime,
        device=device,
        models=models,
        statistics=statistics
    )
