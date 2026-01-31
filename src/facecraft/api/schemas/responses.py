"""Response schemas for the API."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class HealthResponse(BaseModel):
    """Simple health check response."""
    status: str = "healthy"


class ReadyResponse(BaseModel):
    """Readiness check response."""
    ready: bool
    models_loaded: bool


class DeviceInfo(BaseModel):
    """Device information."""
    type: str
    name: Optional[str] = None
    cuda_version: Optional[str] = None


class ModelStatus(BaseModel):
    """Model loading status."""
    loaded: bool
    type: str


class Statistics(BaseModel):
    """Processing statistics."""
    total_processed: int
    success_rate: float
    avg_processing_ms: float


class StatusResponse(BaseModel):
    """Detailed status response."""
    status: str
    version: str
    uptime_seconds: int
    device: DeviceInfo
    models: dict[str, ModelStatus]
    statistics: Statistics


class FacePosition(BaseModel):
    """Face position in image."""
    x: int
    y: int
    width: int
    height: int


class ProcessResult(BaseModel):
    """Processing result details."""
    face_detected: bool
    face_count: int
    face_position: Optional[FacePosition] = None
    output_size: dict[str, int]
    file_size_bytes: int


class ProcessResponse(BaseModel):
    """Single image processing response."""
    success: bool
    job_id: str
    processing_time_ms: int
    result: Optional[ProcessResult] = None
    download_url: Optional[str] = None
    png_url: Optional[str] = None
    jpg_url: Optional[str] = None
    png_base64: Optional[str] = None
    jpg_base64: Optional[str] = None
    error: Optional[str] = None
    error_message: Optional[str] = None


class BatchResultItem(BaseModel):
    """Single item in batch result."""
    filename: str
    success: bool
    download_url: Optional[str] = None
    error: Optional[str] = None
    error_message: Optional[str] = None


class BatchResponse(BaseModel):
    """Batch processing response."""
    job_id: str
    total: int
    successful: int
    failed: int
    processing_time_ms: int
    results: list[BatchResultItem]
