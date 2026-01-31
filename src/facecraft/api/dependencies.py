"""FastAPI dependencies for dependency injection."""

import time
from pathlib import Path
from typing import Optional
from functools import lru_cache

from facecraft.processing.processor import PhotoProcessor
from facecraft.core.config import settings


# Global state
_processor: Optional[PhotoProcessor] = None
_start_time: float = time.time()
_processing_times: list[float] = []


def init_processor() -> PhotoProcessor:
    """Initialize the photo processor with models."""
    global _processor, _start_time

    predictor_path = settings.get_predictor_path()
    codeformer_path = settings.get_codeformer_path()
    device = settings.get_device()

    _processor = PhotoProcessor(
        predictor_path=str(predictor_path) if predictor_path else None,
        codeformer_path=str(codeformer_path) if codeformer_path else None,
        device=device
    )

    _start_time = time.time()
    return _processor


def get_processor() -> PhotoProcessor:
    """Get the photo processor instance."""
    global _processor
    if _processor is None:
        _processor = init_processor()
    return _processor


def get_start_time() -> float:
    """Get the server start time."""
    return _start_time


def get_processing_stats() -> dict:
    """Get processing statistics."""
    processor = get_processor()
    stats = processor.get_stats()

    # Calculate average processing time
    if _processing_times:
        stats['avg_processing_ms'] = sum(_processing_times) / len(_processing_times)
    else:
        stats['avg_processing_ms'] = 0.0

    return stats


def record_processing_time(ms: float):
    """Record a processing time for statistics."""
    global _processing_times
    _processing_times.append(ms)
    # Keep only last 100 measurements
    if len(_processing_times) > 100:
        _processing_times = _processing_times[-100:]


def get_upload_dir() -> Path:
    """Get the upload directory."""
    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def get_output_dir() -> Path:
    """Get the output directory."""
    output_dir = settings.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def cleanup_old_files(max_age_hours: int = 24):
    """Clean up old files from upload and output directories."""
    import os

    now = time.time()
    max_age_seconds = max_age_hours * 3600

    for directory in [settings.upload_dir, settings.output_dir]:
        if not directory.exists():
            continue

        for file_path in directory.rglob("*"):
            if file_path.is_file():
                file_age = now - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    file_path.unlink()
