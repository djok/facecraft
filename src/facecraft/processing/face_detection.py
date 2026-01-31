"""Face detection and alignment using dlib."""

import cv2
import numpy as np
import dlib
from typing import Optional
from pathlib import Path


class FaceDetector:
    """Face detection using dlib's frontal face detector."""

    def __init__(self, predictor_path: Optional[str] = None):
        """
        Initialize the face detector.

        Args:
            predictor_path: Path to dlib shape predictor model for 68-point landmarks.
                          If provided, enables face alignment.
        """
        self.face_detector = dlib.get_frontal_face_detector()
        self.predictor = None

        if predictor_path and Path(predictor_path).exists():
            try:
                self.predictor = dlib.shape_predictor(predictor_path)
            except Exception as e:
                print(f"Warning: Could not load shape predictor: {e}")

    @property
    def has_predictor(self) -> bool:
        """Check if shape predictor is loaded."""
        return self.predictor is not None

    def detect_face(self, image: np.ndarray) -> Optional[dlib.rectangle]:
        """
        Detect face in image.

        Args:
            image: BGR or RGB image

        Returns:
            dlib.rectangle with face position or None if no face found
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Detect faces
        faces = self.face_detector(gray, 1)

        if len(faces) == 0:
            return None

        if len(faces) > 1:
            # Return the largest face
            faces = sorted(faces, key=lambda r: r.width() * r.height(), reverse=True)

        return faces[0]

    def detect_all_faces(self, image: np.ndarray) -> list[dlib.rectangle]:
        """
        Detect all faces in image.

        Args:
            image: BGR or RGB image

        Returns:
            List of dlib.rectangle with face positions
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        faces = self.face_detector(gray, 1)
        return list(faces)

    def get_landmarks(
        self,
        image: np.ndarray,
        face_rect: dlib.rectangle
    ) -> Optional[dlib.full_object_detection]:
        """
        Get 68 facial landmarks for a detected face.

        Args:
            image: BGR or grayscale image
            face_rect: Face bounding box

        Returns:
            68 landmark points or None if predictor not loaded
        """
        if self.predictor is None:
            return None

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        return self.predictor(gray, face_rect)

    def align_face(
        self,
        image: np.ndarray,
        landmarks: dlib.full_object_detection
    ) -> np.ndarray:
        """
        Align face based on eye positions.

        Args:
            image: BGRA image
            landmarks: 68 landmark points

        Returns:
            Aligned image
        """
        # Eye positions (dlib 68-point model)
        left_eye = np.mean(
            [(landmarks.part(i).x, landmarks.part(i).y) for i in range(36, 42)],
            axis=0
        )
        right_eye = np.mean(
            [(landmarks.part(i).x, landmarks.part(i).y) for i in range(42, 48)],
            axis=0
        )

        # Calculate angle
        dx = right_eye[0] - left_eye[0]
        dy = right_eye[1] - left_eye[1]
        angle = np.degrees(np.arctan2(dy, dx))

        # Rotation center (between eyes)
        center = (
            (left_eye[0] + right_eye[0]) / 2,
            (left_eye[1] + right_eye[1]) / 2
        )

        # Rotation matrix
        M = cv2.getRotationMatrix2D(center, angle, 1.0)

        # Apply rotation
        h, w = image.shape[:2]
        aligned = cv2.warpAffine(
            image, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0)
        )

        return aligned

    def crop_face(
        self,
        image: np.ndarray,
        face_rect: dlib.rectangle,
        margin: float = 0.3
    ) -> np.ndarray:
        """
        Crop and center face with margin.

        Args:
            image: BGRA image
            face_rect: Face bounding box
            margin: Margin around face (0.0-1.0)

        Returns:
            Cropped image
        """
        h, w = image.shape[:2]

        face_w = face_rect.width()
        face_h = face_rect.height()

        margin_w = int(face_w * margin)
        margin_h = int(face_h * margin)

        # More margin on top for forehead
        x1 = max(0, face_rect.left() - margin_w)
        y1 = max(0, face_rect.top() - int(margin_h * 1.5))
        x2 = min(w, face_rect.right() + margin_w)
        y2 = min(h, face_rect.bottom() + margin_h)

        return image[y1:y2, x1:x2]
