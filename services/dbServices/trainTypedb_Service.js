const { sql, executeQuery } = require('../../config/db');

async function insertTrainType(trainId, trainType) {

    const query = `
    IF EXISTS (
        SELECT 1
        FROM TrainTypes
        WHERE TrainID = @TrainID
    )
    BEGIN
        UPDATE TrainTypes
        SET
            Traintype = @TrainType,
            DateOfModification = GETDATE()
        WHERE TrainID = @TrainID
    END
    ELSE
    BEGIN
        INSERT INTO TrainTypes
        (
            TrainID,
            Traintype,
            DateOfCreation,
            DateOfModification
        )
        VALUES
        (
            @TrainID,
            @TrainType,
            GETDATE(),
            GETDATE()
        )
    END
    `;

    const params = [
        {
            name: 'TrainID',
            type: sql.NVarChar,
            value: trainId
        },
        {
            name: 'TrainType',
            type: sql.NVarChar,
            value: trainType
        }
    ];

    await executeQuery(query, params);
}

module.exports = {
    insertTrainType
};