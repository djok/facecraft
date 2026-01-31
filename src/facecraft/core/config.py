"""
Configuration management using Pydantic Settings.

All settings can be overridden via environment variables with FACECRAFT_ prefix.
"""

import os
from pathlib import Path
from typing import Optional, Tuple
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Server configuration
    host: str = Field(default="0.0.0.0", alias="FACECRAFT_HOST")
    port: int = Field(default=8000, alias="FACECRAFT_PORT")
    workers: int = Field(default=1, alias="FACECRAFT_WORKERS")
    debug: bool = Field(default=False, alias="FACECRAFT_DEBUG")
    log_level: str = Field(default="INFO", alias="FACECRAFT_LOG_LEVEL")

    # Device configuration
    device: str = Field(default="auto", alias="FACECRAFT_DEVICE")

    # Model paths
    models_dir: Path = Field(default=Path("/app/models"), alias="FACECRAFT_MODELS_DIR")
    predictor_path: Optional[Path] = Field(default=None, alias="FACECRAFT_PREDICTOR_PATH")
    codeformer_path: Optional[Path] = Field(default=None, alias="FACECRAFT_CODEFORMER_PATH")

    # Default processing options
    default_width: int = Field(default=648, alias="FACECRAFT_DEFAULT_WIDTH")
    default_height: int = Field(default=648, alias="FACECRAFT_DEFAULT_HEIGHT")
    default_background_r: int = Field(default=240, alias="FACECRAFT_DEFAULT_BACKGROUND_R")
    default_background_g: int = Field(default=240, alias="FACECRAFT_DEFAULT_BACKGROUND_G")
    default_background_b: int = Field(default=240, alias="FACECRAFT_DEFAULT_BACKGROUND_B")
    default_face_margin: float = Field(default=0.3, alias="FACECRAFT_DEFAULT_FACE_MARGIN")
    default_oval_mask: bool = Field(default=True, alias="FACECRAFT_DEFAULT_OVAL_MASK")
    default_enhance_fidelity: float = Field(default=0.7, alias="FACECRAFT_DEFAULT_ENHANCE_FIDELITY")

    # Storage configuration
    upload_dir: Path = Field(default=Path("/app/uploads"), alias="FACECRAFT_UPLOAD_DIR")
    output_dir: Path = Field(default=Path("/app/processed"), alias="FACECRAFT_OUTPUT_DIR")
    max_upload_size_mb: int = Field(default=20, alias="FACECRAFT_MAX_UPLOAD_SIZE_MB")
    cleanup_age_hours: int = Field(default=24, alias="FACECRAFT_CLEANUP_AGE_HOURS")

    # Performance
    max_concurrent_jobs: int = Field(default=4, alias="FACECRAFT_MAX_CONCURRENT_JOBS")
    batch_max_files: int = Field(default=50, alias="FACECRAFT_BATCH_MAX_FILES")

    # Security
    cors_origins: str = Field(default="*", alias="FACECRAFT_CORS_ORIGINS")
    api_key: Optional[str] = Field(default=None, alias="FACECRAFT_API_KEY")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
        "extra": "ignore",
    }

    @property
    def default_background_color(self) -> Tuple[int, int, int]:
        """Return background color as RGB tuple."""
        return (self.default_background_r, self.default_background_g, self.default_background_b)

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]

    def get_predictor_path(self) -> Optional[Path]:
        """Get predictor path, using default if not explicitly set."""
        if self.predictor_path:
            return self.predictor_path
        default_path = self.models_dir / "shape_predictor_68_face_landmarks.dat"
        return default_path if default_path.exists() else None

    def get_codeformer_path(self) -> Optional[Path]:
        """Get CodeFormer path, using default if not explicitly set."""
        if self.codeformer_path:
            return self.codeformer_path
        default_path = self.models_dir / "codeformer" / "codeformer.pth"
        return default_path if default_path.exists() else None

    def get_device(self) -> str:
        """Determine device to use (cpu or cuda)."""
        if self.device != "auto":
            return self.device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
