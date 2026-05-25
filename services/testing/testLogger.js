const { logger } = require('../../utils/logger'); // adjust path if needed

logger.info("✅ Logger is working");


const { extractTimestamp } = require('../utils/time');

console.log(extractTimestamp("img0085_10_23_13_916766.jpg"));
