from pydantic import BaseModel

class PredictRequest(BaseModel):
    image_path: str   # full path to the image file on the server where the API runs

class PredictResponse(BaseModel):
    is_valid: bool
    class_: str       # e.g. "New Coach" or "Unknown"
    confidence: float