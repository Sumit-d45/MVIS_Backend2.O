// folderScan.js

const fs = require('fs').promises;
const path = require('path');

const ROOT_FOLDERS = [   // later change this path 
  'C:\\Users\\SUMIT\\bv_lh',         
  'C:\\Users\\SUMIT\\bv_rh',           
  'C:\\Users\\SUMIT\\sv_lh',
  'C:\\Users\\SUMIT\\sv_rh'
];  

async function getTrainFolders() {

  const trainFolders = [];

  for (const rootFolder of ROOT_FOLDERS) {

    try {

      const entries = await fs.readdir(
        rootFolder,
        { withFileTypes: true }
      );

      const folders = entries
        .filter(entry => entry.isDirectory())
        .map(entry =>
          path.join(rootFolder, entry.name)
        );

      trainFolders.push(...folders);

    } catch (error) {

      console.error(
        `Error scanning ${rootFolder}:`,
        error.message
      );
    }
  }

  return trainFolders;
}

module.exports = {
  getTrainFolders
};