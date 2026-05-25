const path = require('path');

/**
 * Extract timestamp from image filename
 */
function extractTimestamp(fileName, baseDate) {
  try {
    const name = path.parse(fileName).name;
    const parts = name.split('_');

    if (parts.length < 5) return null;

    const [, hh, mm, ss, micro] = parts;

    const ms = Math.floor(parseInt(micro) / 1000);

    const date = new Date(baseDate);

    date.setHours(parseInt(hh));
    date.setMinutes(parseInt(mm));
    date.setSeconds(parseInt(ss));
    date.setMilliseconds(ms);

    return date;

  } catch (err) {
    return null;
  }
}


module.exports = {
  extractTimestamp
};
