function extractTimestamp(fileName, baseDate) {
  const parts = fileName.split('_');

  const hh = parts[1];
  const mm = parts[2];
  const ss = parts[3];
  const ms = parts[4];

  return new Date(`${baseDate} ${hh}:${mm}:${ss}.${ms}`);
}


//  Build continuous blocks (LOCO + coaches)

function buildCoachBlocks(axleData) {

  const blocks = [];

  let i = 0;

  while (i < axleData.length) {

    const current = axleData[i];

    let axleCount;

    //  Decide block size
    if (current.CoachPosition === 'LOCO') {
      axleCount = 6;
    } else {
      axleCount = 4;
    }

    //  Slice block
    const blockAxles = axleData.slice(i, i + axleCount);

    blocks.push({
      coachPosition: current.CoachPosition,
      axles: blockAxles
    });

    //  Move pointer
    i += axleCount;
  }

  return blocks;
}


//  Assign sequential coach numbers
function assignCoachNumbers(blocks) {
  return blocks.map((block, index) => ({
    coachNumber: index + 1,
    axles: block.axles
  }));
}


//  Find nearest block instead of axle
function findNearestBlock(imageTime, coachBlocks) {
  let minDiff = Infinity;
  let selectedBlock = null;

  for (const block of coachBlocks) {

    for (const axle of block.axles) {

      const axleTime = new Date(axle.SystemTimestamp);
      const diff = Math.abs(imageTime - axleTime);

      if (diff < minDiff) {
        minDiff = diff;
        selectedBlock = block;
      }
    }
  }

  return selectedBlock;
}


//  MAIN FUNCTION
function mapToCoaches(images, axleData, offset, baseDate) {

  // Step 1: Build blocks
  const rawBlocks = buildCoachBlocks(axleData);

  // Step 2: Assign coach numbers
  const coachBlocks = assignCoachNumbers(rawBlocks);

  const mapped = [];

  for (const img of images) {

    const originalTime = extractTimestamp(img.fileName, baseDate);
    const shiftedTime = new Date(originalTime.getTime() + offset);

    // Step 3: Find nearest block
    const block = findNearestBlock(shiftedTime, coachBlocks);

    if (!block) continue;

    mapped.push({
      fileName: img.fileName,
      filePath: img.filePath,
      coach: `Coach_${block.coachNumber}`,
      time: shiftedTime
    });
  }

  return mapped;
}

module.exports = { mapToCoaches };
