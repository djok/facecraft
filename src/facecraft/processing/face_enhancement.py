"""Face enhancement using CodeFormer model."""

import cv2
import numpy as np
import torch
from typing import Optional
from pathlib import Path


class FaceEnhancer:
    """Face quality enhancement using CodeFormer neural network."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "auto"
    ):
        """
        Initialize the face enhancer.

        Args:
            model_path: Path to codeformer.pth model file
            device: Device to use ("cpu", "cuda", or "auto")
        """
        self.codeformer_net = None
        self.face_helper = None
        self.device = self._get_device(device)

        if model_path and Path(model_path).exists():
            self._init_codeformer(model_path)

    def _get_device(self, device: str) -> torch.device:
        """Determine the device to use."""
        if device == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return torch.device(device)

    def _init_codeformer(self, model_path: str):
        """Initialize CodeFormer model."""
        try:
            from facexlib.utils.face_restoration_helper import FaceRestoreHelper
            from facecraft.models.codeformer_arch import CodeFormer

            # Load CodeFormer network
            self.codeformer_net = CodeFormer(
                dim_embd=512,
                codebook_size=1024,
                n_head=8,
                n_layers=9,
                connect_list=['32', '64', '128', '256']
            ).to(self.device)

            # Load weights
            checkpoint = torch.load(model_path, map_location=self.device)
            self.codeformer_net.load_state_dict(checkpoint['params_ema'])
            self.codeformer_net.eval()

            # Face restoration helper
            self.face_helper = FaceRestoreHelper(
                upscale_factor=1,
                face_size=512,
                crop_ratio=(1, 1),
                det_model='retinaface_resnet50',
                save_ext='png',
                use_parse=True,
                device=self.device
            )

        except Exception as e:
            print(f"Warning: Could not initialize CodeFormer: {e}")
            self.codeformer_net = None
            self.face_helper = None

    @property
    def is_available(self) -> bool:
        """Check if face enhancer is ready to use."""
        return self.codeformer_net is not None and self.face_helper is not None

    def enhance(
        self,
        image: np.ndarray,
        fidelity_weight: float = 0.7
    ) -> np.ndarray:
        """
        Enhance face quality using CodeFormer.

        Args:
            image: BGR image from OpenCV
            fidelity_weight: Balance between quality and fidelity (0.0-1.0)
                           Lower = better quality but may alter features
                           Higher = closer to original

        Returns:
            BGR image with enhanced face
        """
        if not self.is_available:
            return image

        try:
            img_original = image.copy()

            # Clean previous results
            self.face_helper.clean_all()

            # Convert BGR -> RGB
            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Detect faces
            self.face_helper.read_image(img_rgb)
            self.face_helper.get_face_landmarks_5(
                only_center_face=False,
                resize=640,
                eye_dist_threshold=5
            )
            self.face_helper.align_warp_face()

            # No faces found
            if len(self.face_helper.cropped_faces) == 0:
                return img_original

            # Process each face
            for cropped_face in self.face_helper.cropped_faces:
                # Normalize input
                cropped_face_t = torch.from_numpy(cropped_face).float() / 255.0
                cropped_face_t = cropped_face_t.permute(2, 0, 1).unsqueeze(0).to(self.device)

                # CodeFormer inference
                with torch.no_grad():
                    output = self.codeformer_net(cropped_face_t, w=fidelity_weight)[0]
                    restored_face = output.squeeze(0).permute(1, 2, 0).cpu().numpy()
                    restored_face = np.clip(restored_face * 255, 0, 255).astype(np.uint8)

                # RGB -> BGR
                restored_face = cv2.cvtColor(restored_face, cv2.COLOR_RGB2BGR)
                self.face_helper.add_restored_face(restored_face)

            # Paste restored faces back
            img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
            self.face_helper.get_inverse_affine(None)

            restored_img = self.face_helper.paste_faces_to_input_image(
                upsample_img=img_bgr,
                draw_box=False
            )

            return restored_img

        except Exception as e:
            print(f"Warning: Face enhancement failed: {e}")
            return image
