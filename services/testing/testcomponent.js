// testcomponentdetection.js

const {
  processComponentDetection
} = require('../detectComponentImage');

(async () => {
  try {
    // Train folder path
    const trainFolderPath =
      'C:\\Users\\SUMIT\\Mvis_bv\\2026_05_15_10_01_26_2000';

    await processComponentDetection(trainFolderPath);

    console .log('✅ Component detection test completed successfully.');
  } catch (error) {
    console.error('❌ Test failed:', error.message);
    console.error(error);
  }
})();