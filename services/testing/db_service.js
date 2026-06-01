const { executeQuery, sql } = require('../../config/db');

/**
 * Check if Train exists
 */
async function checkTrainExists(trainId) {
  console.log(`🔎 Checking Train: ${trainId}`);

  const result = await executeQuery(`
      SELECT COUNT(*) as count 
      FROM TrainTransaction 
      WHERE TrainId = @trainId
  `, [
    { name: 'trainId', type: sql.VarChar, value: trainId }
  ]);

  const exists = result.recordset[0].count > 0;

  console.log(`   👉 Exists: ${exists}`);

  return exists;
}

/**
 * Wait for IsProcessed = 1
 */
async function waitForTrainProcessed(trainId) {
  const MAX_RETRY = 12;
  const DELAY = 10000;

  for (let i = 1; i <= MAX_RETRY; i++) {
    console.log(`⏳ Attempt ${i}/${MAX_RETRY}`);

    const result = await executeQuery(`
        SELECT IsProcessed 
        FROM TrainTransaction 
        WHERE TrainId = @trainId
    `, [
      { name: 'trainId', type: sql.VarChar, value: trainId }
    ]);

    if (result.recordset.length > 0) {
      const status = result.recordset[0].IsProcessed;

      console.log(`   👉 IsProcessed: ${status}`);

      if (status === 1 || status === true) {
      console.log("✅ Train Ready");
      return true;
      }

    }

    await new Promise(res => setTimeout(res, DELAY));
  }

  console.log("❌ Timeout waiting for train");
  return false;
}

/**
 * Get Timeline Data
 */
async function getAxleTimeline(trainId) {
  console.log(`📊 Fetching timeline for ${trainId}`);

  const result = await executeQuery(`
  SELECT 
  AxleNo,
  CoachPosition,
  SystemTimestamp
  FROM TemperatureLog
  WHERE TrainId = @trainId
  AND SystemTimestamp IS NOT NULL
  ORDER BY AxleNo ASC
  
  `, [
    { name: 'trainId', type: sql.VarChar, value: trainId }
  ]);

  console.log(`   👉 Records: ${result.recordset.length}`);

  return result.recordset;
}

module.exports = {
  checkTrainExists,
  waitForTrainProcessed,
  getAxleTimeline
};
