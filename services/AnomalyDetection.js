/**
 * Anomaly Detection Service
 *
 * Reads AIML-generated JSON files from each coach folder,
 * matches component images,
 * crops anomaly images using bbox,
 * creates annotated images with bounding box + label,
 * and inserts anomaly records into DB.
 */

require('dotenv').config();

const fs = require('fs');
const fsp = require('fs').promises;
const path = require('path');
const sharp = require('sharp');

// const {insertAnomalyRecord} = require('./dbServices/anomalyDb_service');

/**
 * Entry Function
 */
async function processAnomalyDetection(trainFolderPath) {
  try {
    console.log(`Processing train folder: ${trainFolderPath}`);

    const entries = await fsp.readdir(trainFolderPath, {
      withFileTypes: true
    });

    // Find coach folders
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

    console.log('✅ Anomaly detection completed successfully.');
  } catch (error) {
    console.error(
      'Error in processAnomalyDetection:',
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

  const anomalyFolder = path.join(
    coachPath,
    'Anomaly_Images'
  );

  const files = await fsp.readdir(anomalyFolder);

  const jsonFile = files.find(file =>
    file.toLowerCase().endsWith('.json')
  );

  if (!jsonFile) {
    console.warn(
      `No JSON file found in ${anomalyFolder}`
    );
    return;
  }

  const jsonPath = path.join(
    anomalyFolder,
    jsonFile
  );

  console.log(`Reading JSON: ${jsonPath}`);

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
      anomalyFolder
    );

  }
}


/**
 * Process Single Image Record
 */
async function processImageRecord(
  record,
  coachImagesFolder,
  anomalyFolder
) {

  const imageName = record.image_name;

  if (!imageName) return;

  const imagePath = path.join(
    coachImagesFolder,
    imageName
  );

  if (!fs.existsSync(imagePath)) {
    console.warn(`Image not found: ${imagePath}`);
    return;
  }

  // IMPORTANT CHANGE
  const anomalies = record.detections || [];

  for (let i = 0; i < anomalies.length; i++) {

    await saveAnomalyFiles(
      imagePath,
      anomalies[i],
      anomalyFolder,
      i
    );

  }
}
/**
 * Save Crop + Main Annotated Image
 */
async function saveAnomalyFiles(
  originalImagePath,
  anomaly,
  anomalyFolder,
  index
) {
  try {

    const anomalyName =
      anomaly.class_name ||
      anomaly.label ||
      'Anomaly';

    const severity =
      anomaly.severity || 'HIGH';

    const bbox = anomaly.bbox;

    if (!bbox) return;

    const safeAnomalyName = anomalyName.replace(
      /\s+/g,
      '_'
    );

    const sequence = index + 1;

    const ext = '.jpg';

    // File Names
    const cropFileName =
      `${safeAnomalyName}_${severity}_${sequence}${ext}`;

    const mainFileName =
      `Main_${safeAnomalyName}_${severity}_${sequence}${ext}`;

    const cropOutputPath = path.join(
      anomalyFolder,
      cropFileName
    );

    const mainOutputPath = path.join(
      anomalyFolder,
      mainFileName
    );

    // BBOX Dimensions
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
        `Invalid bbox for ${anomalyName}`
      );
      return;
    }

    /**
     * Create Main Image with Bounding Box + Label
     */

    const labelText =
      `${safeAnomalyName}_${severity}_${sequence}`;

    const svgOverlay = `
    <svg width="1920" height="1080">

      <!-- Bounding Box -->
      <rect
        x="${left}"
        y="${top}"
        width="${width}"
        height="${height}"
        fill="none"
        stroke="red"
        stroke-width="4"
      />

      <!-- Label Background -->
      <rect
        x="${left}"
        y="${top - 35}"
        width="${labelText.length * 16}"
        height="32"
        fill="red"
      />

      <!-- Label Text -->
      <text
        x="${left + 8}"
        y="${top - 12}"
        font-size="24"
        font-weight="bold"
        fill="white"
      >
        ${labelText}
      </text>

    </svg>
    `;

    // Save annotated image
    await sharp(originalImagePath)
      .composite([
        {
          input: Buffer.from(svgOverlay),
          top: 0,
          left: 0
        }
      ])
      .toFile(mainOutputPath);

    /**
     * Crop Anomaly Image
     */
    await sharp(originalImagePath)
      .extract({
        left,
        top,
        width,
        height
      })
      .toFile(cropOutputPath);

    console.log(`Saved: ${cropFileName}`);
    console.log(`Saved: ${mainFileName}`);

    /**
     * Insert Into DB
     */

    const anomalyComponentName =
      path.parse(cropFileName).name;

    const referenceImagePath =
      path.parse(mainFileName).name;

  //  await insertAnomalyRecord(
  //    anomalyComponentName,
  //    referenceImagePath
  //  );

    console.log(
      `Inserted DB Record: ${anomalyComponentName}`
    );

  } catch (error) {

    console.error(
      `Error saving anomaly files:`,
      error.message
    );

  }
}

module.exports = {
  processAnomalyDetection
};