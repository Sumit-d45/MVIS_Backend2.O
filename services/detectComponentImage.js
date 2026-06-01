/**
 * Component Detection Service
 */

require('dotenv').config();

const fs = require('fs');
const fsp = require('fs').promises;
const path = require('path');
const sharp = require('sharp');
const { executeQuery, sql } = require('../config/db');

const {insertComponentRecord} = require('./dbServices/componentDb_service');

// get train type
async function getTrainType(trainId) {

  const query = `
    SELECT TOP 1 Traintype
    FROM TrainTypes
    WHERE TrainID = @TrainID
  `;

  const result = await executeQuery(query, [
    {
      name: 'TrainID',
      type: sql.NVarChar,
      value: trainId
    }
  ]);

  return result.recordset.length
    ? result.recordset[0].Traintype
    : null;
}

/**
 * Entry Function
 */
async function processComponentDetection(trainFolderPath) {
  try {

    const trainId = path.basename(trainFolderPath);

    const trainFolderLower = trainFolderPath.toLowerCase();

    const side = trainFolderLower.includes('_rh')
    ? 'RH'
    : 'LH';

    const trainType = await getTrainType(trainId);

    if (!trainType) {
      throw new Error(
        `Train Type not found for TrainID: ${trainId}`
      );
    }

    console.log(
      `Processing Train Folder: ${trainFolderPath}`
    );

    console.log(
      `Train Type: ${trainType}`
    );

    const entries = await fsp.readdir(
      trainFolderPath,
      { withFileTypes: true }
    );

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

      await processCoachFolder(
        coachPath,
        trainType,
        side
      );

    }

    console.log(
      '✅ Component Detection Completed'
    );

  } catch (error) {

    console.error(
      'Error in processComponentDetection:',
      error.message
    );

    throw error;
  }
}

/**
 * Process Coach Folder
 */
async function processCoachFolder(
  coachPath,
  trainType,
  side
) {

  const coachImagesFolder = path.join(
    coachPath,
    'Coach_Images'
  );

  const componentFolder = path.join(
    coachPath,
    'Component_Images'
  );

  await fsp.mkdir(componentFolder, {
    recursive: true
  });

  const files = await fsp.readdir(
    componentFolder
  );

  const jsonFile = files.find(file =>
    file.toLowerCase().endsWith('.json')
  );

  if (!jsonFile) {

    console.warn(
      `No JSON File Found In ${componentFolder}`
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

  const imageRecords = Array.isArray(jsonData)
    ? jsonData
    : [jsonData];

  // Track counts + frame processing
  const componentTracker = {};

  for (let frameIndex = 0;
       frameIndex < imageRecords.length;
       frameIndex++) {

    const record = imageRecords[frameIndex];

    await processImageRecord(
        record,
        coachImagesFolder,
        componentFolder,
        trainType,
        componentTracker,
        frameIndex,
        side
      );
  }
}



const componentLimits =  {
            "LHB": {
                "Secondary_Suspension": 2, "Primary_Suspension": 4, "Air_Suspension": 2,
                "Bearing_Assembly_Cover": 4, "Vertical_Damper": 2, "Yaw_Damper": 2,
                "Battery_Box": 1, "Earthing_Wire": 2, "Control_Arm": 4,
                "Wheel": 4, "Buffer": 2, "WSP_Cable": 2, "Fiba_Unit": 1, "Bio_Fule_Tank": 2,
                "Water_Tank": 1, "Junction_Box": 1, "Brake_Panel_Board": 1, "Wraj/plam_System": 1,
                "Running_Gear_Box": 1, "Foot_Board": 2, "Bolt": 8, "Brake_Indicator": 1, "Bearing_Assembly": 4
            },
            "ICF": {
                "Secondary_Suspension": 4, "Primary_Suspension": 8,
                "Battery_Box": 1, "Shock_Absorber": 2, "Wheel": 4, "Buffer": 2, "Bio_Fule_Tank": 2,
                "Water_Tank": 1, "Junction_Box": 1, "Running_Gear_Box": 1, "Foot_Board": 2,
                "Safty_Strap": 8, "Hydral_Waser": 8, "BSS_Hanger": 4, "Bolster": 2, "Bolt": 8,
                "Break_Block": 4, "Lower_Spring_Beam": 2, "Axle_Box_Cover": 4
            },
            "EMU": {
                "Primary_Suspension": 8, "Air_Suspension": 2, "Wheel": 4,
                "Buffer": 2, "Junction_Box": 1, "Foot_Board": 2, "Safty_Strap": 4,
                "Three_Phase_Engine": 1, "AC_DC_Converter": 1, "Axle_Box_Cover": 4, "Bolt": 8,
                "Break_Block": 4, "Fule_Value": 1, "Levelling_Value": 1,
                "Main_Reservoir": 1, "Auxillary_Reservoir": 1, "EP_Unit": 1, "Vertical_Damper": 2
            },
            "WAGON": {
                "Wheel": 4, "CBC": 2, "Bolster": 2, "Spring_Plank": 2, "Bearing_Assembly": 4,
                "Axle_Locking_Key": 4, "Brake_System": 1, "Main_Reservoir": 1,
                "Auxillary_Reservoir": 1, "Side_Frame": 2, "Elastomeric_Pad": 4,
                "Load_Bearing_Spring": 2, "Adapter": 4, "Bolt": 6
            }
        }


const componentRules = 
        {
            "LHB": {
                "default": {"frame_skip": 2, "conf_min": 0.0, "area_min": 0.0},
                "secondary_suspension": {"frame_skip": 10, "conf_min": 0.5, "area_min": 0.6},
                "primary_suspension": {"frame_skip": 3, "conf_min": 0.5, "area_min": 0.3},
                "air_suspension": {"frame_skip": 10, "conf_min": 0.5, "area_min": 0.6},
                "bearing_assembly_cover": {"frame_skip": 3, "conf_min": 0.5, "area_min": 0.4},
                "vertical_damper": {"frame_skip": 10, "conf_min": 0.5, "area_min": 0.3},
                "yaw_damper": {"frame_skip": 10, "conf_min": 0.5, "area_min": 0.3},
                "battery_box": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.6},
                "earthing_wire": {"frame_skip": 6, "conf_min": 0.5, "area_min": 0.3},
                "control_arm": {"frame_skip": 3, "conf_min": 0.3, "area_min": 0.2},
                "wheel": {"frame_skip": 3, "conf_min": 0.5, "area_min": 0.5},
                "buffer": {"frame_skip": 10, "conf_min": 0.5, "area_min": 0.5},
                "wsp_cable": {"frame_skip": 3, "conf_min": 0.3, "area_min": 0.2},
                "fiba_unit": {"frame_skip": 2, "conf_min": 0.3, "area_min": 0.4},
                "bio_fule_tank": {"frame_skip": 10, "conf_min": 0.3, "area_min": 0.4},
                "water_tank": {"frame_skip": 2, "conf_min": 0.3, "area_min": 0.4},
                "junction_box": {"frame_skip": 2, "conf_min": 0.3, "area_min": 0.4},
                "brake_panel_board": {"frame_skip": 2, "conf_min": 0.3, "area_min": 0.4},
                "wraj_palm_system": {"frame_skip": 2, "conf_min": 0.3, "area_min": 0.4},
                "running_gear_box": {"frame_skip": 2, "conf_min": 0.3, "area_min": 0.4},
                "footboard": {"frame_skip": 10, "conf_min": 0.3, "area_min": 0.4},
                "bolt": {"frame_skip": 2, "conf_min": 0.3, "area_min": 0.2},
                "brake_indicator": {"frame_skip": 2, "conf_min": 0.3, "area_min": 0.4},
                "bearing_assembly": {"frame_skip": 3, "conf_min": 0.5, "area_min": 0.4}
            },
            "ICF": {
                "default": {"frame_skip": 2, "conf_min": 0.0, "area_min": 0.0},
                "secondary_suspension": {"frame_skip": 3, "conf_min": 0.5, "area_min": 0.6},
                "primary_suspension": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "battery_box": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "shock_absorber": {"frame_skip": 8, "conf_min": 0.5, "area_min": 0.5},
                "wheel": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "buffer": {"frame_skip": 10, "conf_min": 0.5, "area_min": 0.5},
                "bio_fule_tank": {"frame_skip": 10, "conf_min": 0.5, "area_min": 0.5},
                "water_tank": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "junction_box": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "running_gear_box": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "footboard": {"frame_skip": 10, "conf_min": 0.5, "area_min": 0.5},
                "safty_strap": {"frame_skip": 2, "conf_min": 0.3, "area_min": 0.2},
                "hydral_waser": {"frame_skip": 2, "conf_min": 0.3, "area_min": 0.2},
                "bss_hanger": {"frame_skip": 3, "conf_min": 0.3, "area_min": 0.3},
                "bolster": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "bolt": {"frame_skip": 2, "conf_min": 0.3, "area_min": 0.2},
                "break_block": {"frame_skip": 3, "conf_min": 0.3, "area_min": 0.5},
                "lower_spring_beam": {"frame_skip": 6, "conf_min": 0.5, "area_min": 0.3},
                "axle_box_cover": {"frame_skip": 3, "conf_min": 0.5, "area_min": 0.5}
            },
            "EMU": {
                "default": {"frame_skip": 2, "conf_min": 0.0, "area_min": 0.0},
                "primary_suspension": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "air_suspension": {"frame_skip": 6, "conf_min": 0.5, "area_min": 0.5},
                "wheel": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "buffer": {"frame_skip": 10, "conf_min": 0.5, "area_min": 0.5},
                "junction_box": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "footboard": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "safty_strap": {"frame_skip": 2, "conf_min": 0.3, "area_min": 0.2},
                "three_phase_engine": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "ac_dc_converter": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "axle_box_cover": {"frame_skip": 3, "conf_min": 0.5, "area_min": 0.5},
                "bolt": {"frame_skip": 2, "conf_min": 0.3, "area_min": 0.2},
                "break_block": {"frame_skip": 4, "conf_min": 0.3, "area_min": 0.3},
                "fule_value": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "levelling_value": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "main_reservoir": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "auxillary_reservoir": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "ep_unit": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "vertical_damper": {"frame_skip": 6, "conf_min": 0.5, "area_min": 0.5}
            },
            "WAGON": {
                "default": {"frame_skip": 2, "conf_min": 0.0, "area_min": 0.0},
                "wheel": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "cbc": {"frame_skip": 10, "conf_min": 0.5, "area_min": 0.5},
                "bolster": {"frame_skip": 6, "conf_min": 0.5, "area_min": 0.5},
                "spring_plank": {"frame_skip": 6, "conf_min": 0.5, "area_min": 0.5},
                "bearing_assembly": {"frame_skip": 3, "conf_min": 0.5, "area_min": 0.5},
                "axle_locking_key": {"frame_skip": 3, "conf_min": 0.5, "area_min": 0.5},
                "brake_system": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "main_reservoir": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "auxillary_reservoir": {"frame_skip": 2, "conf_min": 0.5, "area_min": 0.5},
                "side_frame": {"frame_skip": 3, "conf_min": 0.5, "area_min": 0.5},
                "elastomeric_pad": {"frame_skip": 3, "conf_min": 0.5, "area_min": 0.5},
                "load_bearing_spring": {"frame_skip": 6, "conf_min": 0.5, "area_min": 0.5},
                "adapter": {"frame_skip": 3, "conf_min": 0.5, "area_min": 0.5},
                "bolt": {"frame_skip": 2, "conf_min": 0.3, "area_min": 0.2}
            }
        }



/**
 * Process Image Record
 */
async function processImageRecord(
  record,
  coachImagesFolder,
  componentFolder,
  trainType,
  componentTracker,
  frameIndex,
  side
) {

  const imageName = record.image_name;

  if (!imageName) return;

  const imagePath = path.join(
    coachImagesFolder,
    imageName
  );

  if (!fs.existsSync(imagePath)) {

    console.warn(
      `Image Not Found: ${imagePath}`
    );

    return;
  }

  const detections = record.detections || [];

  const trainLimits =
    componentLimits[trainType] || {};

  const trainRules =
    componentRules[trainType] || {};

  for (const detection of detections) {

    const className =
      detection.class_name ||
      detection.label ||
      'Component';

    const normalizedClass =
      className.toLowerCase();

    /**
     * Get Rule
     */
    const rule =
      trainRules[normalizedClass] ||
      trainRules['default'];

    if (!rule) continue;

    const frameSkip =
      rule.frame_skip || 1;

    const confMin =
      rule.conf_min || 0;

    const areaMin =
      rule.area_min || 0;

    /**
     * Get Detection Values
     */
    const confidence =
      detection.confidence || 0;

    const bbox =
      detection.bbox;

    if (!bbox) continue;

    const width =
      bbox.x2 - bbox.x1;

    const height =
      bbox.y2 - bbox.y1;

    const area =
      width * height;

    /**
     * Initialize Tracker
     */
    if (!componentTracker[normalizedClass]) {

      componentTracker[normalizedClass] = {
        count: 0,
        lastFrame: -999
      };
    }

    const tracker =
      componentTracker[normalizedClass];

    /**
     * Frame Skip Logic
     */
    if (
      frameIndex - tracker.lastFrame
      < frameSkip
    ) {

      console.log(
        `Skipping ${className} - frame skip`
      );

      continue;
    }

    /**
     * Confidence Check
     */
    if (confidence < confMin) {

      console.log(
        `Skipping ${className} - low confidence`
      );

      continue;
    }

    /**
     * Area Check
     */
    if (area < areaMin) {

      console.log(
        `Skipping ${className} - low area`
      );

      continue;
    }

    /**
     * Detection Limit Check
     */
    const limit =
      trainLimits[className] || 9999;

    if (tracker.count >= limit) {

      console.log(
        `Skipping ${className} - limit reached`
      );

      continue;
    }

    /**
     * Update Tracker
     */
    tracker.count++;
    tracker.lastFrame = frameIndex;

    /**
     * Save Detection
     */
    await saveDetectionFiles(
      imagePath,
      detection,
      componentFolder,
      tracker.count,
      side
    );
  }
}

/**
 * Save Crop + Main Image
 */
async function saveDetectionFiles(
  originalImagePath,
  detection,
  componentFolder,
  index,
  side
) {

  try {

    const className =
      detection.class_name ||
      detection.label ||
      'Component';

    const imageSide = side;

    const bbox =
      detection.bbox;

    if (!bbox) return;

    const safeClassName =
      className.replace(/\s+/g, '_');

    const ext = '.jpg';

    const cropFileName =
      `${safeClassName}_${imageSide}_${index}${ext}`;

    const mainFileName =
      `Main_${safeClassName}_${imageSide}_${index}${ext}`;

    const cropOutputPath = path.join(
      componentFolder,
      cropFileName
    );

    const mainOutputPath = path.join(
      componentFolder,
      mainFileName
    );

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
        `Invalid BBOX For ${className}`
      );

      return;
    }

    const labelText =
      `${safeClassName}_${imageSide}_${index}`;

    const svgOverlay = `
    <svg width="1920" height="1080">

      <rect
        x="${left}"
        y="${top}"
        width="${width}"
        height="${height}"
        fill="none"
        stroke="lime"
        stroke-width="4"
      />

      <rect
        x="${left}"
        y="${top - 35}"
        width="${labelText.length * 16}"
        height="32"
        fill="lime"
      />

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

    /**
     * Save Main Image
     */
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
     * Save Crop
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
     * Insert DB
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
      'Error Saving Detection Files:',
      error.message
    );
  }
}

module.exports = {processComponentDetection};