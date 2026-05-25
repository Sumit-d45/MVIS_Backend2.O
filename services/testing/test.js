const { scanRawFolders } = require('../file_service');

(async () => {
    const data = await scanRawFolders();

    console.log("\n📦 FINAL OUTPUT:");
    console.log(JSON.stringify(data, null, 2));
    
})();
