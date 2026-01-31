"""Background removal using rembg with u2net_human_seg model."""

import cv2
import numpy as np
from PIL import Image
from rembg import remove, new_session
from typing import Optional


class BackgroundRemover:
    """AI-powered background removal using u2net_human_seg model."""

    def __init__(self, model_name: str = "u2net_human_seg"):
        """
        Initialize the background remover.

        Args:
            model_name: The rembg model to use. Default is u2net_human_seg
                       which is optimized for human segmentation.
        """
        self.session = new_session(model_name)

    def remove_background(self, image: np.ndarray) -> np.ndarray:
        """
        Remove background from an image.

        Args:
            image: BGR image from OpenCV

        Returns:
            BGRA image with transparent background
        """
        # Convert BGR -> RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Convert to PIL Image
        pil_image = Image.fromarray(image_rgb)

        # Remove background
        output = remove(pil_image, session=self.session)

        # Convert back to numpy array (RGBA)
        image_rgba = np.array(output)

        # Convert RGB -> BGR (keeping alpha channel)
        image_bgra = cv2.cvtColor(image_rgba, cv2.COLOR_RGBA2BGRA)

        return image_bgra

    def apply_background_color(
        self,
        image: np.ndarray,
        background_color: tuple[int, int, int]
    ) -> np.ndarray:
        """
        Replace transparent background with a solid color.

        Args:
            image: BGRA image with alpha channel
            background_color: RGB tuple for background

        Returns:
            BGR image with solid background
        """
        if image.shape[2] != 4:
            return image

        # Create BGR background
        result = np.full(
            (image.shape[0], image.shape[1], 3),
            background_color,
            dtype=np.uint8
        )

        # Alpha blending
        alpha = image[:, :, 3:4] / 255.0
        result = (result * (1 - alpha) + image[:, :, 0:3] * alpha).astype(np.uint8)

        return result
