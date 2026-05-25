const fs = require('fs').promises;
const path = require('path');

const OUTPUT_BASE = "C:\\Users\\SUMIT\\Mvis_bv";

async function createCoachFolders(trainId, mappedData) {
  try {
    // Main train folder
    // C:\Users\SUMIT\Mvis_bv\2026_04_17_10_23_09_2000
    const trainFolder = path.join(OUTPUT_BASE, trainId);
    await fs.mkdir(trainFolder, { recursive: true });

    // Group images by coach
    const coachMap = {};

    for (const item of mappedData) {
      if (!coachMap[item.coach]) {
        coachMap[item.coach] = [];
      }
      coachMap[item.coach].push(item);
    }

    // Create coach folders
    for (const coach in coachMap) {
      // Example:
      // coach = "Coach_1"
      // coachSeparationFolder =
      // C:\Users\SUMIT\Mvis_bv\2026_04_17_10_23_09_2000\2026_04_17_10_23_09_2000_Coach_1
      const coachSeparationFolder = path.join(
        trainFolder,
        `${trainId}_${coach}`
      );

      // Create coach separation folder
      await fs.mkdir(coachSeparationFolder, { recursive: true });

      // Create inner "coach" folder
      // C:\Users\SUMIT\Mvis_bv\2026_04_17_10_23_09_2000\2026_04_17_10_23_09_2000_Coach_1\coach
      const coachImageFolder = path.join(coachSeparationFolder, "coach");

      await fs.mkdir(coachImageFolder, { recursive: true });

      console.log(
        `📁 Creating ${coachImageFolder} with ${coachMap[coach].length} images`
      );

      // Copy images into the "coach" folder
      const copyPromises = coachMap[coach].map(async (item) => {
        const destPath = path.join(coachImageFolder, item.fileName);

        try {
          await fs.copyFile(item.filePath, destPath);
        } catch (err) {
          console.warn(`⚠️ Failed copy: ${item.fileName}`);
        }
      });

      await Promise.all(copyPromises);
    }

    console.log("✅ Coach folders created successfully");
  } catch (err) {
    console.error("❌ Folder creation error:", err.message);
  }
}

module.exports = { createCoachFolders };