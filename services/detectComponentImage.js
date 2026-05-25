/**
 * Component Detection Service
 *
 * Reads AIML-generated JSON files from each coach folder,
 * matches coach images,
 * crops component images using bbox,
 * creates annotated images with bounding box + label,
 * and inserts records into DB.
 */

require('dotenv').config();

const fs = require('fs');
const fsp = require('fs').promises;
const path = require('path');
const sharp = require('sharp');

const {
  insertComponentRecord
} = require('./dbServices/componentDb_service');

/**
 * Entry Function
 */
async function processComponentDetection(trainFolderPath) {
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

    console.log('✅ Component detection completed successfully.');
  } catch (error) {
    console.error(
      'Error in processComponentDetection:',
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

  const componentFolder = path.join(
    coachPath,
    'Component_Images'
  );

  // Create Component_Images folder if not exists
  await fsp.mkdir(componentFolder, {
    recursive: true
  });

  // Find JSON file
  const files = await fsp.readdir(componentFolder);

  const jsonFile = files.find(file =>
    file.toLowerCase().endsWith('.json')
  );

  if (!jsonFile) {
    console.warn(
      `No JSON file found in ${componentFolder}`
    );
    return;
  }

  const jsonPath = path.join(
    componentFolder,
    jsonFile
  );

  console.log(`Reading JSON: ${jsonPath}`);

  const jsonContent = await fsp.readFile(
    jsonPath,
    'utf-8'
  );

  const jsonData = JSON.parse(jsonContent);

  // Support array or single object
  const imageRecords = Array.isArray(jsonData)
    ? jsonData
    : [jsonData];

  for (const record of imageRecords) {
    await processImageRecord(
      record,
      coachImagesFolder,
      componentFolder
    );
  }
}

/**
 * Process Single Image Record
 */
async function processImageRecord(
  record,
  coachImagesFolder,
  componentFolder
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

  const detections = record.detections || [];

  for (let i = 0; i < detections.length; i++) {
    await saveDetectionFiles(
      imagePath,
      detections[i],
      componentFolder,
      i
    );
  }
}

/**
 * Save Crop + Main Annotated Image
 */
async function saveDetectionFiles(
  originalImagePath,
  detection,
  componentFolder,
  index
) {
  try {
    const className =
      detection.class_name ||
      detection.label ||
      'Component';

    const side = detection.side || 'LH';

    const bbox = detection.bbox;

    if (!bbox) return;

    const safeClassName = className.replace(
      /\s+/g,
      '_'
    );

    const sequence = index + 1;

    const ext = '.jpg';

    // File names
    const cropFileName =
      `${safeClassName}_${side}_${sequence}${ext}`;

    const mainFileName =
      `Main_${safeClassName}_${side}_${sequence}${ext}`;

    const cropOutputPath = path.join(
      componentFolder,
      cropFileName
    );

    const mainOutputPath = path.join(
      componentFolder,
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
        `Invalid bbox for ${className}`
      );
      return;
    }

    /**
     * Create Main Image with Bounding Box + Label
     */

    const labelText =
      `${safeClassName}_${side}_${sequence}`;

    const svgOverlay = `
    <svg width="1920" height="1080">

      <!-- Bounding Box -->
      <rect
        x="${left}"
        y="${top}"
        width="${width}"
        height="${height}"
        fill="none"
        stroke="lime"
        stroke-width="4"
      />

      <!-- Label Background -->
      <rect
        x="${left}"
        y="${top - 35}"
        width="${labelText.length * 16}"
        height="32"
        fill="lime"
      />

      <!-- Label Text -->
      <text
        x="${left + 8}"
        y="${top - 12}"
        font-size="24"
        font-weight="bold"
        fill="black"
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
     * Crop Component Image
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

    const componentName =
      path.parse(cropFileName).name;

    const referenceImagePath =
      path.parse(mainFileName).name;

    await insertComponentRecord(
      componentName,
      referenceImagePath
    );

    console.log(
      `Inserted DB Record: ${componentName}`
    );
  } catch (error) {
    console.error(
      `Error saving detection files:`,
      error.message
    );
  }
}

module.exports = {
  processComponentDetection
};