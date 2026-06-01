const sql = require('mssql');
const { getPool } = require('../../config/db');

async function updateTrainTransaction(trainId, trainType) {

    const pool = await getPool();

    const coachTypeMap = {
        ICF: 1,
        LHB: 2,
        EMU: 3,
        WAGON: 4
    };

    const coachTypeId = coachTypeMap[trainType.toUpperCase()];

    const result = await pool.request()
        .input('TrainID', sql.NVarChar, trainId)
        .input('MVIS_TrainTypeID', sql.Int, coachTypeId)
        .input('MVIS_TrainName', sql.NVarChar, trainType)
        .query(`
            UPDATE TXN_TrainTransaction
            SET
                MVIS_TrainTypeID = @MVIS_TrainTypeID,
                MVIS_TrainName = @MVIS_TrainName,
                DateOfModification = GETDATE()
            WHERE TrainID = @TrainID
        `);

    if (result.rowsAffected[0] === 0) {
        throw new Error(`TrainID not found: ${trainId}`);
    }
}

module.exports = {
    updateTrainTransaction
};