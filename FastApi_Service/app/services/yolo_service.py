import os
from ultralytics import YOLO

class YOLOService:
    def __init__(self, model_path: str):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found at {model_path}")
        self.model = YOLO(model_path)

    # def predict(self, image_path: str):
    #     """
    #     Run YOLO inference on a single image.
    #     Returns a dict: {
    #         "is_valid": bool,   # True if class is "New Coach"
    #         "class": str,
    #         "confidence": float
    #     }
    #     """
    #     if not os.path.exists(image_path):
    #         raise FileNotFoundError(f"Image not found: {image_path}")

    #     results = self.model(image_path)   # list of Results objects
    #     result = results[0]

    #     # If no detections at all
    #     if result.boxes is None or len(result.boxes) == 0:
    #         return {
    #             "is_valid": False,
    #             "class": "Unknown",
    #             "confidence": 0.0
    #         }

    #     # Take the detection with highest confidence
    #     boxes = result.boxes
    #     # boxes.conf, boxes.cls, boxes.xyxy
    #     confidences = boxes.conf.cpu().numpy()
    #     class_ids = boxes.cls.cpu().numpy().astype(int)

    #     # Highest confidence index
    #     best_idx = confidences.argmax()
    #     best_class_id = class_ids[best_idx]
    #     best_conf = float(confidences[best_idx])

    #     # Map class id to name (model.names is a dict like {0: "New Coach", 1: "Unknown"})
    #     class_name = self.model.names.get(best_class_id, "Unknown")

    #     is_valid = (class_name == "New Coach")

    #     return {
    #         "is_valid": is_valid,
    #         "class": class_name,
    #         "confidence": round(best_conf, 4)
        # }

    def predict(self, image_path: str):
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        results = self.model(image_path)
        result = results[0]

        if result.boxes is None or len(result.boxes) == 0:
            return {
                "is_valid": False,   # no detection at all -> not valid
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

        # ✅ CHANGE: Both "New Coach" and "Unknown" are considered valid
        is_valid = (class_name == "New Coach" or class_name == "Unknown")

        return {
            "is_valid": is_valid,
            "class": class_name,
            "confidence": round(best_conf, 4)
        }


# Singleton instance
_model_service = None

def get_model_service():
    global _model_service
    if _model_service is None:
        # Adjust path if needed – here it assumes the model is inside app/models/
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(base_dir, "models", "BV_coach_separation_model_14_0.pt")
        _model_service = YOLOService(model_path)
    return _model_service