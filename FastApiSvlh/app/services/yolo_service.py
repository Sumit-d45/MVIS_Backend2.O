import os
import torch
from ultralytics import YOLO


class YOLOService:
    def __init__(self, model_path: str):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found at {model_path}")

        # 🔥 FIX: force weights_only=False
        original_load = torch.load

        def patched_load(*args, **kwargs):
            kwargs["weights_only"] = False
            return original_load(*args, **kwargs)

        torch.load = patched_load

        try:
            self.model = YOLO(model_path)
        except Exception as e:
            raise RuntimeError(f"Failed to load YOLO model: {str(e)}")

    def predict(self, image_path: str):
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        try:
            results = self.model(image_path)
            result = results[0]

            if result.boxes is None or len(result.boxes) == 0:
                return {
                    "is_valid": False,
                    "class": "Unknown",
                    "confidence": 0.0
                }

            boxes = result.boxes
            confidences = boxes.conf.cpu().numpy()
            class_ids = boxes.cls.cpu().numpy().astype(int)

            best_idx = confidences.argmax()
            best_class_id = class_ids[best_idx]
            best_conf = float(confidences[best_idx])

            class_name = self.model.names.get(best_class_id, "Unknown")

            return {
                "is_valid": class_name in ["New Coach", "Unknown"],
                "class": class_name,
                "confidence": round(best_conf, 4)
            }

        except Exception as e:
            raise RuntimeError(f"Model inference error: {str(e)}")


_model_service = None


def get_model_service():
    global _model_service

    if _model_service is None:
        model_path = r"C:\\Users\SUMIT\\Mvis_backend\\FastApiSvlh\\app\\models\side_view_coach_separation_model_15_0.pt"
        _model_service = YOLOService(model_path)

    return _model_service

