const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '../../processed.txt');

/**
 * Read processed trains
 */
function getProcessedTrains() {
  if (!fs.existsSync(filePath)) return [];

  const data = fs.readFileSync(filePath, 'utf-8');
  return data.split('\n').filter(Boolean);
}

/**
 * Check if already processed
 */
function isProcessed(trainId) {
  const processed = getProcessedTrains();
  return processed.includes(trainId);
}

/**
 * Mark as processed
 */
function markProcessed(trainId) {
  fs.appendFileSync(filePath, trainId + '\n');
}

module.exports = {
  isProcessed,
  markProcessed
};
