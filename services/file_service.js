/*

const fs = require('fs').promises;
const path = require('path');
const { extractTimestamp } = require('../utils/time');


const RAW_BASE = "C:\\Users\\SUMIT\\MVC_BV_LH"; // change later to MVC paths

const IMAGE_EXT = ['.jpg', '.jpeg', '.png'];


// Check if folder contains images

async function getImages(dirPath) {
    const files = await fs.readdir(dirPath);

    return files.filter(file =>
        IMAGE_EXT.includes(path.extname(file).toLowerCase())
    );
}


// Smart scan (handles both flat + nested)

async function scanRawFolders(basePath = RAW_BASE) {
    console.log(`\n🚀 Scanning: ${basePath}\n`);

    const items = await fs.readdir(basePath, { withFileTypes: true });

    const trains = [];

    for (const item of items) {
        if (!item.isDirectory()) continue;

        const folderPath = path.join(basePath, item.name);

        const images = await getImages(folderPath);

        // ✅ Case 1: Folder itself is train
        if (images.length > 0) {
            console.log(`🚆 Train detected: ${item.name}`);
            console.log(`   👉 Images: ${images.length}`);

            trains.push({
                trainId: item.name,
                trainPath: folderPath
            });

            continue;
        }

        // ✅ Case 2: Nested (zip case)
        const subItems = await fs.readdir(folderPath, { withFileTypes: true });

        for (const sub of subItems) {
            if (!sub.isDirectory()) continue;

            const subPath = path.join(folderPath, sub.name);

            const subImages = await getImages(subPath);

            if (subImages.length > 0) {
                console.log(`🚆 Train detected (nested): ${sub.name}`);
                console.log(`   👉 Images: ${subImages.length}`);

                trains.push({
                    trainId: sub.name,
                    trainPath: subPath
                });
            }
        }
    }

    console.log(`\n✅ Total trains found: ${trains.length}`);

    return trains;
}

module.exports = {
    scanRawFolders
};


*/

const fs = require('fs').promises;
const path = require('path');
const { extractTimestamp } = require('../utils/time');

const RAW_BASE = "C:\\Users\\SUMIT\\MVC_BV_LH"; // later replace with multiple paths
// const RAW_BASE = "C:\\Users\\SUMIT\\MVC_SV_LH"

const IMAGE_EXT = ['.jpg', '.jpeg', '.png'];


// Get images with metadata

async function getImages(dirPath) {
    try {
        const files = await fs.readdir(dirPath);

        return files
            .filter(file =>
                IMAGE_EXT.includes(path.extname(file).toLowerCase())
            )
            .sort((a, b) => a.localeCompare(b))   //  sort filenames first
            .map(file => ({
                fileName: file,
                filePath: path.join(dirPath, file),
                timestamp: extractTimestamp(file) //  important
            }))
            .filter(img => img.timestamp !== null); // ✅ remove invalid
    } catch (err) {
        console.error(`❌ Error reading images from ${dirPath}:`, err.message);
        return [];
    }
}

// Scan RAW folders (handles flat + nested structure)

async function scanRawFolders(basePath = RAW_BASE) {
    console.log(`\n🚀 Scanning: ${basePath}\n`);

    let items;

    try {
        items = await fs.readdir(basePath, { withFileTypes: true });
    } catch (err) {
        console.error(`❌ Failed to read base path: ${err.message}`);
        return [];
    }

    const trains = [];

    for (const item of items) {
        if (!item.isDirectory()) continue;

        const folderPath = path.join(basePath, item.name);

        const images = await getImages(folderPath);

        // ✅ Case 1: Direct train folder
        if (images.length > 0) {
            console.log(`🚆 Train detected: ${item.name}`);
            console.log(`   👉 Images: ${images.length}`);

            trains.push({
                trainId: item.name,
                trainPath: folderPath,
                images
            });

            continue;
        }

        // ✅ Case 2: Nested folders (zip extracted case)
        let subItems;

        try {
            subItems = await fs.readdir(folderPath, { withFileTypes: true });
        } catch (err) {
            console.error(`❌ Failed reading nested folder: ${folderPath}`);
            continue;
        }

        for (const sub of subItems) {
            if (!sub.isDirectory()) continue;

            const subPath = path.join(folderPath, sub.name);

            const subImages = await getImages(subPath);

            if (subImages.length > 0) {
                console.log(`🚆 Train detected (nested): ${sub.name}`);
                console.log(`   👉 Images: ${subImages.length}`);

                trains.push({
                    trainId: sub.name,
                    trainPath: subPath,
                    images: subImages
                });
            }
        }
    }

    console.log(`\n✅ Total trains found: ${trains.length}`);

    return trains;
}

module.exports = {
    scanRawFolders,
    getImages
};
