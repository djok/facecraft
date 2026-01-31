"""Custom exceptions for Facecraft API."""


class FacecraftError(Exception):
    """Base exception for Facecraft."""
    pass


class NoFaceDetectedError(FacecraftError):
    """Raised when no face is detected in the image."""
    pass


class MultipleFacesDetectedError(FacecraftError):
    """Raised when multiple faces are detected (if single face required)."""
    pass


class ImageProcessingError(FacecraftError):
    """Raised when image processing fails."""
    pass


class ModelLoadError(FacecraftError):
    """Raised when a model fails to load."""
    pass


class InvalidImageError(FacecraftError):
    """Raised when the input image is invalid or corrupted."""
    pass


class FileTooLargeError(FacecraftError):
    """Raised when uploaded file exceeds size limit."""
    pass
