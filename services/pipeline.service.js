
/*
const { scanRawFolders } = require('./file_service');
const {checkTrainExists,waitForTrainProcessed,getAxleTimeline} = require('./db_service');
const { detectAllCoaches } = require('./fastapi.service');
const { mapToCoaches } = require('./coachMapper_service');
const { createCoachFolders } = require('./coachfolder');

// Main Pipeline

async function processPipeline() {
  console.log("\n Starting Pipeline...\n");

  // 1️⃣ Scan RAW folders
  const trains = await scanRawFolders();

  if (!trains.length) {
    console.log(" No trains found");
    return;
  }

  // 2️⃣ Process each train
  for (const train of trains) {
    const trainId = train.trainId;

    console.log("\n==============================");
    console.log(` Processing Train: ${trainId}`);
    console.log("==============================");

    try {
      // 3️⃣ Check Train Exists
      const exists = await checkTrainExists(trainId);

      if (!exists) {
        console.log(" Train not found in DB, skipping...");
        continue;
      }

      // 4️⃣ Wait for IsProcessed
      const ready = await waitForTrainProcessed(trainId);

      if (!ready) {
        console.log(" Train not ready, skipping...");
        continue;
      }
      
      
      // wait for 90 sec
      console.log(" Waiting additional 90 seconds...");
      await new Promise(res => setTimeout(res, 90000));

      // 5️⃣ Fetch Timeline
      const timeline = await getAxleTimeline(trainId);

      if (!timeline.length) {
        console.log(" No timeline data, skipping...");
        continue;
      }

      console.log(` Pipeline ready for Train: ${trainId}`);

      // 🔜 NEXT STEP (later)
      // call FastAPI here
      // process images
      // map to coaches

      const detections = await detectAllCoaches(train.images);

      if (!detections.length) {
      console.log(" No detections");
      continue;
    }

const mapped = mapToCoaches(detections);

console.log(" Coach Mapping Sample:", mapped.slice(0, 5));
//  DEBUG (add here)
console.log(" Last 10 mappings:", mapped.slice(-10));


//  FINAL STEP
await createCoachFolders(trainId, mapped);

console.log(" Coach separation completed");



    } catch (err) {
      console.error(` Error processing train ${trainId}:`, err.message);
    }
  }


  console.log("\n Pipeline Completed\n");
}

module.exports = {
  processPipeline
};

*/
const { scanRawFolders } = require('./file_service');
const { checkTrainExists, waitForTrainProcessed, getAxleTimeline } = require('./testing/db_service');
const { detectValidImages } = require('./fastapi.service'); // ✅ FIXED
const { mapToCoaches } = require('./coachMapper_service');
const { createCoachFolders } = require('./coachfolder');
const { isProcessed, markProcessed } = require('../utils/processed');
const { logger } = require('../utils/logger');


// 🔹 Extract timestamp from filename
function extractTimestamp(fileName, baseDate) {
  const parts = fileName.split('_');

  const hh = parts[1];
  const mm = parts[2];
  const ss = parts[3];
  const ms = parts[4];

  return new Date(`${baseDate} ${hh}:${mm}:${ss}.${ms}`);
}


async function processPipeline() {
  logger.info(" Starting Pipeline...");

  try {
    const trains = await scanRawFolders();

    if (!trains.length) {
      logger.warn(" No trains found");
      return;
    }

    logger.info(`Total trains detected: ${trains.length}`);

    for (const train of trains) {

      const trainId = train.trainId;

      logger.info("=================================");
      logger.info(` Processing Train: ${trainId}`);
      logger.info("=================================");

      try {

      //  if (isProcessed(trainId)) {
      //    logger.warn(` Skipping already processed: ${trainId}`);
      //    continue;
      //  }

        const exists = await checkTrainExists(trainId);
        if (!exists) {
          logger.warn(` Train not found in DB: ${trainId}`);
          continue;
        }

        const ready = await waitForTrainProcessed(trainId);
        if (!ready) {
          logger.warn(` Train not ready: ${trainId}`);
          continue;
        }

        // ✅ 90 sec wait
      //  logger.info(" Waiting additional 90 seconds...");
      //  await new Promise(res => setTimeout(res, 90000));

        // ✅ Fetch DB timeline
        const timeline = await getAxleTimeline(trainId);

        if (!timeline.length) {
          logger.warn(` No timeline data: ${trainId}`);
          continue;
        }

        logger.info(` Timeline records: ${timeline.length}`);


         const baseDate = train.trainId.split('_')[0]; // adjust if needed

        // Step 1: get valid images
        const validImages = await detectValidImages(train.images,baseDate);

      if (!validImages.length) {
      logger.warn(` No valid images: ${trainId}`);
      continue;
      } 

      logger.info(` First valid image: ${validImages[0].fileName}`);

        // 🔥 STEP 2: Extract image timestamp
        const imageTime = extractTimestamp(validImages[0].fileName, baseDate);

        // get db time 
        const dbTime = new Date(timeline[0].SystemTimestamp).getTime();

        // offset calculation
        const offset = dbTime - imageTime.getTime();


        logger.info(` Offset calculated: ${offset} ms`);

        // 🔥 STEP 5: Map ALL images using offset + DB
        const mapped = mapToCoaches(
          validImages,
          timeline,
          offset,
          baseDate
        );

        if (!mapped.length) {
          logger.warn(` No mapped images: ${trainId}`);
          continue;
        }

        logger.info(` Total mapped images: ${mapped.length}`);

        // 🔥 STEP 6: Create folders
        await createCoachFolders(trainId, mapped);

        logger.info(" Coach separation completed");

        // 🔥 STEP 7: Mark processed
      //  markProcessed(trainId);
      //  logger.info(` Marked processed: ${trainId}`);

      } catch (err) {
        logger.error(` Error processing train ${trainId}: ${err.message}`);
      }
    }

  } catch (err) {
    logger.error(` Pipeline failed: ${err.message}`);
  }

  logger.info(" Pipeline Completed");
}

module.exports = {
  processPipeline
};



