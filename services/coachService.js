const fs = require('fs').promises;
const path = require('path');

async function getCoachFolders(trainId) {
    const trainFolder = path.join(
        'C:\\Users\\SUMIT\\Mvis_bv',
        trainId
    );

    const entries = await fs.readdir(trainFolder, {
        withFileTypes: true
    });

    return entries
        .filter(
            entry =>
                entry.isDirectory() &&
                entry.name.includes('_Coach_')
        )
        .map(entry => ({
            coachId: entry.name,
            coachPath: path.join(trainFolder, entry.name)
        }));
}

module.exports = {
    getCoachFolders
};