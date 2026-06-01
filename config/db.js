
const path = require('path');
const sql = require('mssql');

require('dotenv').config({
  path: path.join(__dirname, '.env')
});

// Debug
console.log('DB_SERVER:', process.env.DB_SERVER);
console.log('DB_DATABASE:', process.env.DB_DATABASE);
console.log('DB_USER:', process.env.DB_USER);

const config = {
  server: process.env.DB_SERVER,
  database: process.env.DB_DATABASE,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  port: parseInt(process.env.DB_PORT || '1433'),
  options: {
    encrypt: false,
    trustServerCertificate: true
  }
};

let pool;

async function getPool() {
  if (!pool) {
    pool = await new sql.ConnectionPool(config).connect();
    console.log('✅ DB Connected');
  }
  return pool;
}

async function executeQuery(query, params = []) {
  const pool = await getPool();
  const request = pool.request();

  params.forEach(param => {
    request.input(param.name, param.type, param.value);
  });

  return request.query(query);
}

async function executeStoredProcedure(procedureName, params = []) {
  const pool = await getPool();
  const request = pool.request();

  params.forEach(param => {
    request.input(param.name, param.type, param.value);
  });

  return request.execute(procedureName);
}

module.exports = {
  sql,
  getPool,
  executeQuery,
  executeStoredProcedure
};

