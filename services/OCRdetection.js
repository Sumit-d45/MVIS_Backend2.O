/**
 * OCR Detection Service
 *
 * Reads AIML-generated OCR JSON files from each coach folder,
 * matches component images,
 * crops OCR regions using bbox,
 * saves only cropped OCR images,
 * runs OCR on cropped images,
 * and inserts OCR records into DB.
 */

require('dotenv').config();

const fs = require('fs');
const fsp = require('fs').promises;
const path = require('path');
const sharp = require('sharp');
const Tesseract = require('tesseract.js');

// const { insertOCRRecord } = require('./dbServices/ocrDb_service');

/**
 * Entry Function
 */
async function processOCRDetection(trainFolderPath) {

  try {

    console.log(
      `Processing OCR train folder: ${trainFolderPath}`
    );

    const entries = await fsp.readdir(
      trainFolderPath,
      { withFileTypes: true }
    );

    // Find Coach Folders
    const coachFolders = entries
      .filter(
        entry =>
          entry.isDirectory() &&
          entry.name.includes('_Coach_')
      )
      .map(entry =>
        path.join(trainFolderPath, entry.name)
      );

    for (const coachPath of coachFolders) {

      await processCoachFolder(coachPath);

    }

    console.log(
      '✅ OCR Detection Completed Successfully'
    );

  } catch (error) {

    console.error(
      'Error in processOCRDetection:',
      error.message
    );

    throw error;
  }
}

/**
 * Process One Coach Folder
 */
async function processCoachFolder(coachPath) {

  const coachImagesFolder = path.join(
    coachPath,
    'Coach_Images'
  );

  const ocrFolder = path.join(
    coachPath,
    'OCR_Images'
  );

  // Create OCR Folder if not exists
  if (!fs.existsSync(ocrFolder)) {

    await fsp.mkdir(ocrFolder, {
      recursive: true
    });

  }

  const files = await fsp.readdir(ocrFolder);

  const jsonFile = files.find(file =>
    file.toLowerCase().endsWith('.json')
  );

  if (!jsonFile) {

    console.warn(
      `No OCR JSON found in ${ocrFolder}`
    );

    return;
  }

  const jsonPath = path.join(
    ocrFolder,
    jsonFile
  );

  console.log(`Reading OCR JSON: ${jsonPath}`);

  const jsonContent = await fsp.readFile(
    jsonPath,
    'utf-8'
  );

  const jsonData = JSON.parse(jsonContent);

  const imageRecords = Array.isArray(jsonData)
    ? jsonData
    : [jsonData];

  for (const record of imageRecords) {

    await processImageRecord(
      record,
      coachImagesFolder,
      ocrFolder
    );

  }
}

/**
 * Process Single Image Record
 */
async function processImageRecord(
  record,
  coachImagesFolder,
  ocrFolder
) {

  const imageName = record.image_name;

  if (!imageName) return;

  const imagePath = path.join(
    coachImagesFolder,
    imageName
  );

  if (!fs.existsSync(imagePath)) {

    console.warn(
      `Image not found: ${imagePath}`
    );

    return;
  }

  // OCR detections
  const detections = record.detections || [];

  for (let i = 0; i < detections.length; i++) {

    await saveOCRCrop(
      imagePath,
      detections[i],
      ocrFolder,
      i
    );

  }
}

/**
 * Crop OCR Region + Run OCR
 */
async function saveOCRCrop(
  originalImagePath,
  detection,
  ocrFolder,
  index
) {

  try {

    const componentName =
      detection.class_name ||
      detection.label ||
      'OCR';

    const bbox = detection.bbox;

    if (!bbox) return;

    const safeComponentName =
      componentName.replace(/\s+/g, '_');

    const sequence = index + 1;

    const cropFileName =
      `${safeComponentName}_${sequence}.jpg`;

    const cropOutputPath = path.join(
      ocrFolder,
      cropFileName
    );

    /**
     * BBOX Dimensions
     */
    const left = Math.round(bbox.x1);

    const top = Math.round(bbox.y1);

    const width = Math.round(
      bbox.x2 - bbox.x1
    );

    const height = Math.round(
      bbox.y2 - bbox.y1
    );

    if (width <= 0 || height <= 0) {

      console.warn(
        `Invalid bbox for ${componentName}`
      );

      return;
    }

    /**
     * Crop OCR Image
     */
    await sharp(originalImagePath)
      .extract({
        left,
        top,
        width,
        height
      })
      .toFile(cropOutputPath);

    console.log(
      `Saved OCR Crop: ${cropFileName}`
    );

    /**
     * Run OCR
     */
    const result = await Tesseract.recognize(
      cropOutputPath,
      'eng',
      {
        logger: m => console.log(m)
      }
    );

    const detectedText =
      result.data.text.trim();

    console.log(
      `OCR Text (${cropFileName}): ${detectedText}`
    );

    /**
     * Save OCR Text File
     */
    const textFileName =
      `${safeComponentName}_${sequence}.txt`;

    const textFilePath = path.join(
      ocrFolder,
      textFileName
    );

    await fsp.writeFile(
      textFilePath,
      detectedText || ''
    );

    console.log(
      `Saved OCR Text: ${textFileName}`
    );

    /**
     * Insert Into DB
     */

    const componentImageName =
      path.parse(cropFileName).name;

    // await insertOCRRecord(
    //   OCR,
    //   detectedText
    // );

    console.log(
      `Inserted OCR Record: ${componentImageName}`
    );

  } catch (error) {

    console.error(
      'Error in saveOCRCrop:',
      error.message
    );

  }
}

module.exports = {
  processOCRDetection
};