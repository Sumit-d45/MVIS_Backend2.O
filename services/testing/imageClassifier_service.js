require('dotenv').config();

const fs = require('fs');
const path = require('path');
const axios = require('axios');
const FormData = require('form-data');
const pLimit = require('p-limit');


const limit = pLimit(5);

// ===============================
// 📁 Create Subfolders
// ===============================
function createSubFolders(coachPath) {
    const folders = [
        'Anomaly_Images',
        'OCR_Images',
        'Component_Images',
        'Coach_Images'
    ];

    folders.forEach(folder => {
        const fullPath = path.join(coachPath, folder);
        if (!fs.existsSync(fullPath)) {
            fs.mkdirSync(fullPath, { recursive: true });
        }
    });
}

// ===============================
// 📤 Create Form Data
// ===============================
function createForm(imagePath) {
    const form = new FormData();
    form.append('file', fs.createReadStream(imagePath));
    return form;
}

// ===============================
// 📡 Call APIs (Parallel)
// ===============================
async function callAllAPIs(imagePath) {
    try {
        const anomalyReq = axios.post(
            process.env.ANOMALY_API,
            createForm(imagePath),
            { headers: createForm(imagePath).getHeaders(), timeout: 10000 }
        );

        const ocrReq = axios.post(
            process.env.OCR_API,
            createForm(imagePath),
            { headers: createForm(imagePath).getHeaders(), timeout: 10000 }
        );

        const componentReq = axios.post(
            process.env.COMPONENT_API,
            createForm(imagePath),
            { headers: createForm(imagePath).getHeaders(), timeout: 10000 }
        );

        const coachReq = axios.post(
            process.env.COACH_API,
            createForm(imagePath),
            { headers: createForm(imagePath).getHeaders(), timeout: 10000 }
        );

        const [anomaly, ocr, component, coach] = await Promise.allSettled([
            anomalyReq,
            ocrReq,
            componentReq,
            coachReq
        ]);

        return {
            anomaly: anomaly.status === 'fulfilled' ? anomaly.value.data : null,
            ocr: ocr.status === 'fulfilled' ? ocr.value.data : null,
            component: component.status === 'fulfilled' ? component.value.data : null,
            coach: coach.status === 'fulfilled' ? coach.value.data : null
        };

    } catch (error) {
        console.error("API Error:", error.message);
        return {};
    }
}

// ===============================
// 🧠 Decide Category
// ===============================
function decideCategory(result) {
    if (result?.anomaly?.detected) return 'Anomaly_Images';
    if (result?.ocr?.textDetected) return 'OCR_Images';
    if (result?.component?.found) return 'Component_Images';
    return 'Coach_Images';
}

// ===============================
// 📂 Copy Image
// ===============================
function copyImageToFolder(imagePath, coachPath, category) {
    const fileName = path.basename(imagePath);
    const destPath = path.join(coachPath, category, fileName);

    fs.copyFileSync(imagePath, destPath);
}

// ===============================
// 🔁 Process Single Image
// ===============================
async function processSingleImage(imagePath, coachPath) {
    try {
        const result = await callAllAPIs(imagePath);
        const category = decideCategory(result);

        copyImageToFolder(imagePath, coachPath, category);

        console.log(`✅ Processed: ${path.basename(imagePath)} → ${category}`);

    } catch (error) {
        console.error(`❌ Error processing ${imagePath}:`, error.message);
    }
}

// ===============================
// 🚀 Process Coach Images
// ===============================
async function processCoachImages(coachPath, images) {
    try {
        createSubFolders(coachPath);

        await Promise.all(
            images.map(img =>
                limit(() => processSingleImage(img, coachPath))
            )
        );

        console.log(`🎯 Completed Coach: ${coachPath}`);

    } catch (error) {
        console.error("Coach Processing Error:", error.message);
    }
}

// ===============================
// 📦 Export Service
// ===============================
module.exports = {
    processCoachImages
};
