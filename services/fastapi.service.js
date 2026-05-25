
/*

const axios = require('axios');
const { logger } = require('../utils/logger');

const FASTAPI_URL = "http://127.0.0.1:8000";


// 🔹 Call FastAPI YOLO prediction
async function predict(imagePath) {
  try {
    const response = await axios.post(
      `${FASTAPI_URL}/predict`,
      { image_path: imagePath },
      { timeout: 5000 }
    );

    return response.data;

  } catch (error) {
    logger.error(`FastAPI error: ${error.message}`);
    return null;
  }
}


// 🔹 Retry wrapper
async function predictWithRetry(imagePath, retries = 2) {

  for (let i = 0; i <= retries; i++) {

    const result = await predict(imagePath);

    if (result) return result;

    logger.warn(`Retry ${i + 1} for ${imagePath}`);
  }

  return null;
}


// 🔥 MAIN FUNCTION → Filter only valid images
async function detectValidImages(images) {

  logger.info("Running YOLO to filter valid images...");

  const results = [];

  const MAX_IMAGES = 4000;
  const BATCH_SIZE = 25;

  const limitedImages = images.slice(0, MAX_IMAGES);

  for (let i = 0; i < limitedImages.length; i += BATCH_SIZE) {

    const batch = limitedImages.slice(i, i + BATCH_SIZE);

    logger.info(`Processing batch ${i / BATCH_SIZE + 1}`);

    // Parallel API calls
    const promises = batch.map(img => predictWithRetry(img.filePath));
    const responses = await Promise.all(promises);

    for (let j = 0; j < responses.length; j++) {

      const result = responses[j];
      const img = batch[j];

      if (!result) continue;

      console.log(`🖼️ ${img.fileName} →`, result);

      // 🔥 FILTER LOGIC (IMPORTANT)
      if (result.is_valid === true && result.class_ === 'Unknown') {

        results.push({
          fileName: img.fileName,
          filePath: img.filePath,
          confidence: result.confidence
        });

      }
    }
  }

  logger.info(`Total valid images: ${results.length}`);

  return results;
}


module.exports = {
  predict,
  detectValidImages
};

*/

// using p-limit


const axios = require('axios');
const pLimit = require('p-limit').default;
const { logger } = require('../utils/logger');

const FASTAPI_URL = "http://127.0.0.1:8000";


// 🔹 Extract timestamp (needed for sorting)
function extractTimestamp(fileName, baseDate) {
  const parts = fileName.split('_');

  const hh = parts[1];
  const mm = parts[2];
  const ss = parts[3];
  const ms = parts[4];

  return new Date(`${baseDate} ${hh}:${mm}:${ss}.${ms}`);
}


// 🔹 Call FastAPI YOLO prediction
async function predict(imagePath) {
  try {
    const response = await axios.post(
      `${FASTAPI_URL}/predict`,
      { image_path: imagePath },
      { timeout: 5000 }
    );

    return response.data;

  } catch (error) {
    logger.error(`FastAPI error: ${error.message}`);
    return null;
  }
}


// 🔹 Retry wrapper
async function predictWithRetry(imagePath, retries = 2) {

  for (let i = 0; i <= retries; i++) {

    const result = await predict(imagePath);

    if (result) return result;

    logger.warn(`Retry ${i + 1} for ${imagePath}`);
  }

  return null;
}


//  MAIN FUNCTION → Optimized with p-limit
async function detectValidImages(images, baseDate) {

  logger.info("Running YOLO with controlled concurrency...");

  const MAX_IMAGES = 4000;
  const CONCURRENCY = 20; //  tune (15–25)

  const limit = pLimit(CONCURRENCY);

  const limitedImages = images.slice(0, MAX_IMAGES);

  console.time("YOLO Processing");

  //  Controlled parallel execution
  const tasks = limitedImages.map(img =>
    limit(async () => {

      const result = await predictWithRetry(img.filePath);

      if (!result) return null;

      console.log(`🖼️ ${img.fileName} →`, result);

      //  FILTER LOGIC
      if (result.is_valid === true && result.class_ === 'Unknown') {
        return {
          fileName: img.fileName,
          filePath: img.filePath,
          confidence: result.confidence
        };
      }

      return null;
    })
  );

  // Wait for all tasks
  const responses = await Promise.all(tasks);

  console.timeEnd("YOLO Processing");

  //  Remove nulls
  let validImages = responses.filter(Boolean);

  //  VERY IMPORTANT → sort by timestamp
  validImages.sort((a, b) => {
    return extractTimestamp(a.fileName, baseDate) -
           extractTimestamp(b.fileName, baseDate);
  });

  logger.info(`Total valid images: ${validImages.length}`);

  return validImages;
}


module.exports = {
  predict,
  detectValidImages
};

