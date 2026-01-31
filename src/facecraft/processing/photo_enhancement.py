"""Photo enhancement for professional portrait quality."""

import cv2
import numpy as np
from PIL import Image, ImageEnhance


class PhotoEnhancer:
    """Professional photo enhancement for portrait photography."""

    def enhance(self, image: np.ndarray) -> np.ndarray:
        """
        Apply professional enhancements for portrait quality.

        Args:
            image: BGRA or BGR image

        Returns:
            Enhanced image (same format as input)
        """
        # Separate BGR and alpha channel
        bgr = image[:, :, :3]
        alpha = image[:, :, 3] if image.shape[2] == 4 else None

        # 1. Auto exposure correction
        bgr = self._auto_exposure(bgr)

        # 2. Noise reduction (bilateral filter preserves edges)
        bgr = cv2.bilateralFilter(bgr, d=5, sigmaColor=40, sigmaSpace=40)

        # 3. Auto white balance
        bgr = self._auto_white_balance(bgr)

        # 4. Sharpening
        kernel = np.array([
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0]
        ])
        bgr = cv2.filter2D(bgr, -1, kernel)

        # 5. Contrast and saturation adjustment
        pil_img = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))

        # Moderate contrast boost
        enhancer = ImageEnhance.Contrast(pil_img)
        pil_img = enhancer.enhance(1.15)

        # Moderate saturation boost
        enhancer = ImageEnhance.Color(pil_img)
        pil_img = enhancer.enhance(1.15)

        # Convert back to OpenCV format
        bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        # Restore alpha channel if present
        if alpha is not None:
            return np.dstack([bgr, alpha])
        return bgr

    def _auto_exposure(self, image: np.ndarray) -> np.ndarray:
        """
        Intelligent auto exposure correction using LAB color space.

        Args:
            image: BGR image

        Returns:
            Exposure-corrected BGR image
        """
        # Convert to LAB
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # Analyze histogram
        mean_brightness = np.mean(l)

        # Target brightness for professional portraits
        target_brightness = 140

        brightness_diff = target_brightness - mean_brightness

        if abs(brightness_diff) > 10:
            # Adaptive correction with CLAHE
            clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
            l_clahe = clahe.apply(l)

            # Blend original and CLAHE
            alpha_blend = min(abs(brightness_diff) / 50.0, 0.7)
            l = cv2.addWeighted(l, 1 - alpha_blend, l_clahe, alpha_blend, 0)

            # Gamma correction for dark images
            if brightness_diff > 20:
                gamma = min(1.0 + (brightness_diff / 200.0), 1.4)
                inv_gamma = 1.0 / gamma
                table = np.array([
                    ((i / 255.0) ** inv_gamma) * 255
                    for i in np.arange(0, 256)
                ]).astype("uint8")
                l = cv2.LUT(l, table)

        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def _auto_white_balance(self, image: np.ndarray) -> np.ndarray:
        """
        Auto white balance using Gray World algorithm.

        Args:
            image: BGR image

        Returns:
            White-balanced BGR image
        """
        result = image.copy()

        # Calculate mean of each channel
        avg_b = np.mean(result[:, :, 0])
        avg_g = np.mean(result[:, :, 1])
        avg_r = np.mean(result[:, :, 2])

        # Calculate gray value
        gray = (avg_b + avg_g + avg_r) / 3

        # Scale each channel
        scale_b = min(gray / avg_b if avg_b > 0 else 1.0, 1.5)
        scale_g = min(gray / avg_g if avg_g > 0 else 1.0, 1.5)
        scale_r = min(gray / avg_r if avg_r > 0 else 1.0, 1.5)

        result[:, :, 0] = np.clip(result[:, :, 0] * scale_b, 0, 255)
        result[:, :, 1] = np.clip(result[:, :, 1] * scale_g, 0, 255)
        result[:, :, 2] = np.clip(result[:, :, 2] * scale_r, 0, 255)

        return result.astype(np.uint8)


class OvalMask:
    """Apply oval mask for professional portrait cropping."""

    @staticmethod
    def apply(image: np.ndarray, feather: int = 21) -> np.ndarray:
        """
        Apply oval mask with transparent background.

        Args:
            image: BGR or BGRA image
            feather: Feathering amount for smooth edges

        Returns:
            BGRA image with oval mask
        """
        h, w = image.shape[:2]

        # Convert to BGRA if needed
        if len(image.shape) == 2 or image.shape[2] == 3:
            bgra = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
        else:
            bgra = image.copy()

        # Create oval mask
        mask = np.zeros((h, w), dtype=np.uint8)

        center_x = w // 2
        center_y = h // 2

        radius_x = int(w * 0.48)
        radius_y = int(h * 0.48)

        # Draw filled ellipse
        cv2.ellipse(mask, (center_x, center_y), (radius_x, radius_y), 0, 0, 360, 255, -1)

        # Feather edges
        mask_blurred = cv2.GaussianBlur(mask, (feather, feather), feather // 2)

        # Apply mask to alpha channel
        bgra[:, :, 3] = cv2.multiply(bgra[:, :, 3], mask_blurred, scale=1/255.0)

        return bgra


class ImageResizer:
    """Resize images while preserving aspect ratio."""

    @staticmethod
    def resize_with_padding(
        image: np.ndarray,
        target_size: tuple[int, int],
        background_color: tuple[int, int, int] = (240, 240, 240),
        use_transparent: bool = False
    ) -> np.ndarray:
        """
        Resize image with padding to maintain aspect ratio.

        Args:
            image: BGR or BGRA image
            target_size: (width, height)
            background_color: RGB color for padding
            use_transparent: Use transparent background (BGRA output)

        Returns:
            Resized image
        """
        h, w = image.shape[:2]
        target_w, target_h = target_size

        # Calculate scale ratio
        ratio = min(target_w / w, target_h / h)
        new_w = int(w * ratio)
        new_h = int(h * ratio)

        # Resize
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

        # Create canvas
        if use_transparent:
            canvas = np.zeros((target_h, target_w, 4), dtype=np.uint8)
        else:
            canvas = np.full((target_h, target_w, 3), background_color, dtype=np.uint8)

        # Center the image
        y_offset = (target_h - new_h) // 2
        x_offset = (target_w - new_w) // 2

        # Handle alpha channel
        if len(resized.shape) == 3 and resized.shape[2] == 4:
            if use_transparent:
                canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
            else:
                alpha = resized[:, :, 3] / 255.0
                for c in range(3):
                    canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w, c] = (
                        canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w, c] * (1 - alpha) +
                        resized[:, :, c] * alpha
                    )
        else:
            if use_transparent:
                bgra = cv2.cvtColor(resized, cv2.COLOR_BGR2BGRA)
                canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = bgra
            else:
                canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized

        return canvas
