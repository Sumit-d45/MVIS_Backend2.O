from fastapi import APIRouter, HTTPException
from app.schemas.request_response import PredictRequest, PredictResponse
from app.services.yolo_service import get_model_service

router = APIRouter()

@router.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    try:
        service = get_model_service()
        result = service.predict(request.image_path)
        return PredictResponse(
            is_valid=result["is_valid"],
            class_=result["class"],
            confidence=result["confidence"]
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model inference error: {str(e)}")