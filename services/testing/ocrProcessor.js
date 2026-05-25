
// Logic:
// 1. Call AIML OCR detection API with image path or image file.
// 2. Get bounding box coordinates for OCR region.
// 3. Crop OCR region from original image.
// 4. Run OCR on cropped image using Tesseract.
// 5. Return extracted text and saved cropped image path.

const fs = require("fs");
const path = require("path");
const axios = require("axios");
const sharp = require("sharp");
const Tesseract = require("tesseract.js");

// AIML API URL
const OCR_DETECTION_API = "http://127.0.0.1:8000/detect-ocr";

/**
 * Call AIML OCR detection API
 * Expected response format:
 * {
 *   "detections": [
 *     {
 *       "bbox": {
 *         "x1": 100,
 *         "y1": 50,
 *         "x2": 900,
 *         "y2": 300
 *       },
 *       "confidence": 0.98
 *     }
 *   ]
 * }
 */
async function callOCRDetectionAPI(imagePath) {
  const formData = new FormData();
  formData.append("file", fs.createReadStream(imagePath));

  const response = await axios.post(OCR_DETECTION_API, formData, {
    headers: formData.getHeaders(),
    maxBodyLength: Infinity,
  });

  return response.data;
}

/**
 * Crop OCR image using Sharp
 */
async function cropOCRImage(imagePath, bbox, outputPath) {
  const width = bbox.x2 - bbox.x1;
  const height = bbox.y2 - bbox.y1;

  await sharp(imagePath)
    .extract({
      left: Math.max(0, Math.round(bbox.x1)),
      top: Math.max(0, Math.round(bbox.y1)),
      width: Math.round(width),
      height: Math.round(height),
    })
    .toFile(outputPath);

  return outputPath;
}

/**
 * Read text from cropped image
 */
async function readOCRText(croppedImagePath) {
  const {
    data: { text },
  } = await Tesseract.recognize(croppedImagePath, "eng", {
    logger: (m) => console.log(m.status, m.progress),
  });

  // Remove spaces and line breaks
  return text.replace(/\s+/g, "").trim();
}

/**
 * Main processing function
 */
async function processOCRImage(imagePath, outputFolder) {
  try {
    // Ensure output folder exists
    fs.mkdirSync(outputFolder, { recursive: true });

    // Step 1: Detect OCR region
    const apiResult = await callOCRDetectionAPI(imagePath);

    if (
      !apiResult.detections ||
      apiResult.detections.length === 0
    ) {
      console.log("No OCR region detected.");
      return null;
    }

    // Use highest confidence detection
    const detection = apiResult.detections.sort(
      (a, b) => b.confidence - a.confidence
    )[0];

    const bbox = detection.bbox;

    // Step 2: Crop image
    const fileName = path.parse(imagePath).name;
    const croppedImagePath = path.join(
      outputFolder,
      `${fileName}_ocr.png`
    );

    await cropOCRImage(imagePath, bbox, croppedImagePath);

    // Step 3: Read OCR text
    const ocrText = await readOCRText(croppedImagePath);

    console.log("Cropped OCR Image:", croppedImagePath);
    console.log("Detected Text:", ocrText);

    return {
      croppedImagePath,
      ocrText,
      bbox,
      confidence: detection.confidence,
    };
  } catch (error) {
    console.error("OCR processing failed:", error.message);
    throw error;
  }
}

module.exports = {
  processOCRImage,
};