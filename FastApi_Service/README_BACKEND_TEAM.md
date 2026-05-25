# Coach Separation Model API – Documentation for Backend Team

## Overview

This API wraps a YOLO deep learning model that detects whether a given train image shows a **"New Coach"** (i.e., the start of a new coach).  
It is built with FastAPI and runs as a separate microservice. Your Node.js orchestrator will call this API whenever it needs to classify an image.

## Base URL

Once running: `http://<server-ip>:8000`

## Endpoints

### 1. Health Check

**GET** `/health`

Response:
```json
{
  "status": "ok",
  "model_loaded": true
}