"""Request schemas for the API."""

from pydantic import BaseModel, Field
from typing import Optional


class OutputOptions(BaseModel):
    """Output format options."""
    width: int = Field(default=648, ge=64, le=4096)
    height: int = Field(default=648, ge=64, le=4096)
    max_size_kb: Optional[int] = Field(default=99, ge=10, le=1000)


class BackgroundOptions(BaseModel):
    """Background options."""
    color_r: int = Field(default=240, ge=0, le=255)
    color_g: int = Field(default=240, ge=0, le=255)
    color_b: int = Field(default=240, ge=0, le=255)
    transparent: bool = Field(default=True)


class FaceOptions(BaseModel):
    """Face processing options."""
    enhance: bool = Field(default=True)
    enhance_fidelity: float = Field(default=0.7, ge=0.0, le=1.0)
    margin: float = Field(default=0.3, ge=0.0, le=1.0)


class PhotoOptions(BaseModel):
    """Photo enhancement options."""
    enhance: bool = Field(default=True)
    oval_mask: bool = Field(default=True)


class ProcessingOptionsRequest(BaseModel):
    """Full processing options for API requests."""
    output: OutputOptions = OutputOptions()
    background: BackgroundOptions = BackgroundOptions()
    face: FaceOptions = FaceOptions()
    photo: PhotoOptions = PhotoOptions()
    return_base64: bool = Field(default=False)

    def to_processing_options(self):
        """Convert to internal ProcessingOptions."""
        from facecraft.processing.processor import ProcessingOptions
        return ProcessingOptions(
            width=self.output.width,
            height=self.output.height,
            background_color=(
                self.background.color_r,
                self.background.color_g,
                self.background.color_b
            ),
            face_margin=self.face.margin,
            use_oval_mask=self.photo.oval_mask,
            enhance_face=self.face.enhance,
            enhance_fidelity=self.face.enhance_fidelity,
            enhance_photo=self.photo.enhance,
            max_jpeg_size_kb=self.output.max_size_kb
        )
