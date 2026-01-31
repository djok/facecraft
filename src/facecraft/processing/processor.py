"""Main photo processor that combines all processing modules."""

import os
import cv2
import numpy as np
from typing import Optional
from pathlib import Path
from dataclasses import dataclass, field

from .background import BackgroundRemover
from .face_detection import FaceDetector
from .face_enhancement import FaceEnhancer
from .photo_enhancement import PhotoEnhancer, OvalMask, ImageResizer


@dataclass
class ProcessingResult:
    """Result of photo processing."""
    success: bool
    face_detected: bool = False
    face_count: int = 0
    face_position: Optional[dict] = None
    output_path: Optional[str] = None
    png_path: Optional[str] = None
    jpg_path: Optional[str] = None
    file_size_bytes: int = 0
    error: Optional[str] = None


@dataclass
class ProcessingOptions:
    """Options for photo processing."""
    width: int = 648
    height: int = 648
    background_color: tuple[int, int, int] = (240, 240, 240)
    face_margin: float = 0.3
    use_oval_mask: bool = True
    enhance_face: bool = True
    enhance_fidelity: float = 0.7
    enhance_photo: bool = True
    max_jpeg_size_kb: Optional[int] = 99


class PhotoProcessor:
    """
    Main processor for portrait photo enhancement.

    Combines background removal, face detection, alignment,
    and enhancement into a single processing pipeline.
    """

    def __init__(
        self,
        predictor_path: Optional[str] = None,
        codeformer_path: Optional[str] = None,
        device: str = "auto"
    ):
        """
        Initialize the photo processor.

        Args:
            predictor_path: Path to dlib shape predictor model
            codeformer_path: Path to CodeFormer model
            device: Device for ML models ("cpu", "cuda", or "auto")
        """
        # Initialize components
        self.background_remover = BackgroundRemover()
        self.face_detector = FaceDetector(predictor_path)
        self.face_enhancer = FaceEnhancer(codeformer_path, device)
        self.photo_enhancer = PhotoEnhancer()

        # Statistics
        self.stats = {
            'total': 0,
            'success': 0,
            'no_face': 0,
            'errors': 0
        }

    @property
    def has_face_alignment(self) -> bool:
        """Check if face alignment is available."""
        return self.face_detector.has_predictor

    @property
    def has_face_enhancement(self) -> bool:
        """Check if face enhancement is available."""
        return self.face_enhancer.is_available

    def process_image(
        self,
        input_path: str,
        output_path: str,
        options: Optional[ProcessingOptions] = None
    ) -> ProcessingResult:
        """
        Process a single image through the full pipeline.

        Args:
            input_path: Path to input image
            output_path: Path for output image
            options: Processing options

        Returns:
            ProcessingResult with details about the processing
        """
        self.stats['total'] += 1
        options = options or ProcessingOptions()

        try:
            # 1. Load image
            image = cv2.imread(input_path)
            if image is None:
                raise ValueError(f"Could not load image: {input_path}")

            # 2. Face enhancement (CodeFormer)
            if options.enhance_face and self.face_enhancer.is_available:
                image = self.face_enhancer.enhance(image, options.enhance_fidelity)

            # 3. Detect face
            face_rect = self.face_detector.detect_face(image)
            if face_rect is None:
                self.stats['no_face'] += 1
                return ProcessingResult(
                    success=False,
                    face_detected=False,
                    error="no_face_detected"
                )

            face_position = {
                'x': face_rect.left(),
                'y': face_rect.top(),
                'width': face_rect.width(),
                'height': face_rect.height()
            }

            # 4. Remove background
            image_no_bg = self.background_remover.remove_background(image)

            # 5. Align face (if predictor available)
            landmarks = None
            if self.face_detector.has_predictor:
                landmarks = self.face_detector.get_landmarks(image, face_rect)
                if landmarks is not None:
                    image_no_bg = self.face_detector.align_face(image_no_bg, landmarks)
                    # Re-detect face after alignment
                    new_face_rect = self.face_detector.detect_face(image_no_bg)
                    if new_face_rect is not None:
                        face_rect = new_face_rect

            # 6. Crop and center face
            cropped = self.face_detector.crop_face(
                image_no_bg,
                face_rect,
                options.face_margin
            )

            # 7. Photo enhancement
            if options.enhance_photo:
                enhanced = self.photo_enhancer.enhance(cropped)
            else:
                enhanced = cropped

            # 8. Apply oval mask
            if options.use_oval_mask:
                enhanced = OvalMask.apply(enhanced)

            # 9. Resize with padding
            final = ImageResizer.resize_with_padding(
                enhanced,
                (options.width, options.height),
                options.background_color,
                use_transparent=options.use_oval_mask
            )

            # 10. Save output
            result = self._save_output(
                final,
                output_path,
                options
            )

            self.stats['success'] += 1
            result.face_detected = True
            result.face_count = 1
            result.face_position = face_position

            return result

        except Exception as e:
            self.stats['errors'] += 1
            return ProcessingResult(
                success=False,
                error=str(e)
            )

    def _save_output(
        self,
        image: np.ndarray,
        output_path: str,
        options: ProcessingOptions
    ) -> ProcessingResult:
        """Save the processed image."""
        result = ProcessingResult(success=True)
        output_dir = os.path.dirname(output_path)
        base_name = Path(output_path).stem

        # Save PNG (with transparency if oval mask)
        if options.use_oval_mask:
            png_path = os.path.join(output_dir, f"{base_name}.png")
            cv2.imwrite(png_path, image, [cv2.IMWRITE_PNG_COMPRESSION, 9])
            result.png_path = png_path
            result.output_path = png_path
            result.file_size_bytes = os.path.getsize(png_path)

        # Save JPEG copy
        jpg_dir = os.path.join(output_dir, 'jpg')
        os.makedirs(jpg_dir, exist_ok=True)
        jpg_path = os.path.join(jpg_dir, f"{base_name}.jpg")

        # Convert BGRA to BGR with background
        if image.shape[2] == 4:
            jpeg_image = np.full(
                (image.shape[0], image.shape[1], 3),
                options.background_color,
                dtype=np.uint8
            )
            alpha = image[:, :, 3:4] / 255.0
            jpeg_image = (jpeg_image * (1 - alpha) + image[:, :, 0:3] * alpha).astype(np.uint8)
        else:
            jpeg_image = image

        # Adaptive quality for size limit
        if options.max_jpeg_size_kb:
            quality = 90
            max_size_bytes = options.max_jpeg_size_kb * 1024
            cv2.imwrite(jpg_path, jpeg_image, [cv2.IMWRITE_JPEG_QUALITY, quality])

            while os.path.getsize(jpg_path) > max_size_bytes and quality > 50:
                quality -= 3
                cv2.imwrite(jpg_path, jpeg_image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        else:
            cv2.imwrite(jpg_path, jpeg_image, [cv2.IMWRITE_JPEG_QUALITY, 90])

        result.jpg_path = jpg_path

        if not options.use_oval_mask:
            result.output_path = jpg_path
            result.file_size_bytes = os.path.getsize(jpg_path)

        return result

    def process_image_bytes(
        self,
        image_bytes: bytes,
        options: Optional[ProcessingOptions] = None
    ) -> tuple[Optional[bytes], Optional[bytes], ProcessingResult]:
        """
        Process an image from bytes.

        Args:
            image_bytes: Image data as bytes
            options: Processing options

        Returns:
            Tuple of (png_bytes, jpg_bytes, result)
        """
        import tempfile
        import uuid

        options = options or ProcessingOptions()

        # Save to temp file
        temp_id = str(uuid.uuid4())[:8]
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, f"input_{temp_id}.jpg")
            output_path = os.path.join(temp_dir, f"output_{temp_id}.png")

            # Write input
            with open(input_path, 'wb') as f:
                f.write(image_bytes)

            # Process
            result = self.process_image(input_path, output_path, options)

            if not result.success:
                return None, None, result

            # Read outputs
            png_bytes = None
            jpg_bytes = None

            if result.png_path and os.path.exists(result.png_path):
                with open(result.png_path, 'rb') as f:
                    png_bytes = f.read()

            if result.jpg_path and os.path.exists(result.jpg_path):
                with open(result.jpg_path, 'rb') as f:
                    jpg_bytes = f.read()

            return png_bytes, jpg_bytes, result

    def get_stats(self) -> dict:
        """Get processing statistics."""
        stats = self.stats.copy()
        if stats['total'] > 0:
            stats['success_rate'] = stats['success'] / stats['total']
        else:
            stats['success_rate'] = 0.0
        return stats

    def reset_stats(self):
        """Reset processing statistics."""
        self.stats = {
            'total': 0,
            'success': 0,
            'no_face': 0,
            'errors': 0
        }
