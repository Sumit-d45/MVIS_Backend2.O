from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import json
import shutil

app = FastAPI()

# --------------------------------------------------
# Static folder for annotated images
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
ANNOTATED_DIR = BASE_DIR / "annotated"
ANNOTATED_DIR.mkdir(parents=True, exist_ok=True)

# Expose annotated images at:
# http://127.0.0.1:8000/annotated/<filename>
app.mount(
    "/annotated",
    StaticFiles(directory=ANNOTATED_DIR),
    name="annotated"
)


# --------------------------------------------------
# Request Model
# --------------------------------------------------
class RequestModel(BaseModel):
    folder_path: str


# --------------------------------------------------
# Component Detection API
# --------------------------------------------------
@app.post("/component")
def run_component_detection(req: RequestModel):
    train_folder = Path(req.folder_path)

    if not train_folder.exists():
        return {
            "status": "error",
            "message": "Folder not found"
        }

    # Find all coach folders
    coach_folders = [
        p for p in train_folder.iterdir()
        if p.is_dir() and "Coach" in p.name
    ]

    for coach_folder in coach_folders:
        coach_images_folder = coach_folder / "coach"
        json_folder = coach_folder / "JSON response"
        json_folder.mkdir(parents=True, exist_ok=True)

        if not coach_images_folder.exists():
            continue

        # Read all JPG images
        images = list(coach_images_folder.glob("*.jpg"))

        for image in images:
            # --------------------------------------------------
            # Create annotated image (copy original image)
            # --------------------------------------------------
            annotated_name = f"{image.stem}_annotated.jpg"
            annotated_path = ANNOTATED_DIR / annotated_name

            shutil.copy(image, annotated_path)

            # --------------------------------------------------
            # Create sample JSON response
            # --------------------------------------------------
            sample_json = {
                "image_name": image.name,
                "total_detections": 2,
                "detections": [
                    {
                        "class_name": "Bio_Fule_Tank",
                        "confidence": 0.95,
                        "bbox": {
                            "x1": 100,
                            "y1": 100,
                            "x2": 500,
                            "y2": 400
                        }
                    },
                    {
                        "class_name": "Foot_Board",
                        "confidence": 0.88,
                        "bbox": {
                            "x1": 600,
                            "y1": 200,
                            "x2": 1000,
                            "y2": 500
                        }
                    }
                ],
                "annotated_image_url": f"/annotated/{annotated_name}"
            }

            # --------------------------------------------------
            # Save JSON file in:
            # Coach_X/JSON response/<image_name>.json
            # --------------------------------------------------
            json_path = json_folder / f"{image.stem}.json"

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(sample_json, f, indent=2)

    return {
        "status": "success",
        "message": "Dummy component detection completed"
    }