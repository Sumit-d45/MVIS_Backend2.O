const { sql, getPool } = require('../../config/db');

async function insertCoach(
    trainId,
    coachId,
    coachTypeId,
    coachImagePath
) {
    const pool = await getPool();

    await pool.request()
        .input('TrainID', sql.NVarChar, trainId)
        .input('CoachID', sql.NVarChar, coachId)
        .input('MVIS_CoachTypeID', sql.Int, coachTypeId)
        .input('MVIS_CoachImagePath', sql.NVarChar, coachImagePath)
        .query(`
            INSERT INTO TXN_Coach
            (
                TrainID,
                CoachID,
                MVIS_CoachTypeID,
                MVIS_CoachImagePath
            )
            VALUES
            (
                @TrainID,
                @CoachID,
                @MVIS_CoachTypeID,
                @MVIS_CoachImagePath
            )
        `);
}

module.exports = {
    insertCoach
};