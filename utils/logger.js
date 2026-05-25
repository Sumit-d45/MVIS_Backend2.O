const winston = require('winston');
const fs = require('fs');
const path = require('path');

const logDirectory = path.join(__dirname, '../../logs');

if (!fs.existsSync(logDirectory)) {
  fs.mkdirSync(logDirectory, { recursive: true });
}

// Custom filter
const filterLevel = (level) =>
  winston.format((info) => (info.level === level ? info : false))();

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    // ✅ All logs
    new winston.transports.File({
      filename: path.join(logDirectory, 'combined.log')
    }),

    // ❌ Errors only
    new winston.transports.File({
      filename: path.join(logDirectory, 'error.log'),
      level: 'error'
    }),

    // 🚆 Pipeline logs
    new winston.transports.File({
      filename: path.join(logDirectory, 'pipeline.log'),
      format: winston.format.combine(
        filterLevel('info'),
        winston.format.json()
      )
    }),

    // ⚙️ System logs
    new winston.transports.File({
      filename: path.join(logDirectory, 'system.log'),
      format: winston.format.combine(
        filterLevel('warn'),
        winston.format.json()
      )
    })
  ]
});

// Console (dev)
if (process.env.NODE_ENV !== 'production') {
  logger.add(new winston.transports.Console({
    format: winston.format.simple()
  }));
}

module.exports = { logger };
