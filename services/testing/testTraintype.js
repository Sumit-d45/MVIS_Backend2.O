const { processTrainTypeJson } = require('../traintype');

(async () => {
    await processTrainTypeJson(
        'C:\\Users\\SUMIT\\Mvis_bv\\2026_05_15_10_01_26_2000\\trainType.json'
    );
})();