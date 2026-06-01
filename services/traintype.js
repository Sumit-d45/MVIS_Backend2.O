const fs = require('fs').promises;
const { insertTrainType } = require('./dbServices/trainTypedb_Service');
const { updateTrainTransaction } = require('./dbServices/trainTransactiondb_Service');
const { getCoachFolders } = require('./coachService');
const { insertCoach } = require('./dbServices/coachdb_Service');

async function processTrainTypeJson(jsonPath) {

    const content = await fs.readFile(jsonPath, 'utf8');
    const data = JSON.parse(content);

    if (!data.trainid || !data.traintype) {
        throw new Error('Invalid TrainType JSON');
    }

    await insertTrainType(
        data.trainid,
        data.traintype
    );

    await updateTrainTransaction(
        data.trainid,
        data.traintype
    );

    const coachTypeMap = {
        ICF: 1,
        LHB: 2,
        EMU: 3,
        WAGON: 4
    };

    const coachTypeId =
        coachTypeMap[data.traintype.toUpperCase()];

    const coaches = await getCoachFolders(
        data.trainid
    );

    for (const coach of coaches) {

        await insertCoach(
            data.trainid,
            coach.coachId,
            coachTypeId,
            coach.coachPath
        );

        console.log(`Inserted Coach: ${coach.coachId}`);
    }

    console.log(
        `✅ Train Type inserted and TrainTransaction updated : ${data.trainid} -> ${data.traintype}`
    );
}

module.exports = {
    processTrainTypeJson
};