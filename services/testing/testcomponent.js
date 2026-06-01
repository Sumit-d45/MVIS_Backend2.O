const {
  getTrainFolders
} = require('../folderScan');

const {
  processComponentDetection
} = require('../detectComponentImage');

(async () => {

  try {

    const trainFolders =
      await getTrainFolders();

    console.log(
      `Found ${trainFolders.length} train folders`
    );

    for (const trainFolder of trainFolders) {

      console.log(
        `\nProcessing: ${trainFolder}`
      );

      await processComponentDetection(
        trainFolder
      );

      console.log(
        `Completed: ${trainFolder}`
      );
    }

    console.log(
      '\n✅ Component Detection Test Completed'
    );

  } catch (error) {

    console.error(
      '\n❌ Component Detection Test Failed'
    );

    console.error(error);
  }

})();