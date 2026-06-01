// testcomponentdetection.js

const {
  processAnomalyDetection
} = require('../AnomalyDetection');

(async () => {
  try {
    // Train folder path
    const trainFolderPath =
      'C:\\Users\\SUMIT\\Mvis_bv\\2026_05_15_10_01_26_2000';

    await processAnomalyDetection(trainFolderPath);

    console .log('✅ Anomaly detection test completed successfully.');
  } catch (error) {
    console.error('❌ Test failed:', error.message);
    console.error(error);
  }
})();