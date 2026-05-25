from fastapi import FastAPI
from app.routes import predict

app = FastAPI(
    title="Coach Separation YOLO Model API",
    description="Detects 'New Coach' in train images. Used by Node.js orchestrator.",
    version="1.0"
)

app.include_router(predict.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "model_loaded": True}