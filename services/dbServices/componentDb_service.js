// services/dbServices/componentDb_service.js

const { sql, executeQuery } = require('../../config/db');

async function insertComponentRecord(
  componentName,
  referenceImagePath,
  viewType = 'Bogi View'
) {
  // Generate component code from component name
  // Example: Axle_Box_Cover_LH_1 -> AXLE_BOX_COVER_LH_1
  const componentCode = componentName.toUpperCase();

  // Active flag
  const isActive = true;

  const query = `
    INSERT INTO MST_Component (
      ComponentCode,
      ComponentName,
      ReferenceImagePath,
      ViewType,
      IsActive
    )
    VALUES (
      @ComponentCode,
      @ComponentName,
      @ReferenceImagePath,
      @ViewType,
      @IsActive
    )
  `;

  const params = [
    {
      name: 'ComponentCode',
      type: sql.NVarChar(100),
      value: componentCode
    },
    {
      name: 'ComponentName',
      type: sql.NVarChar(200),
      value: componentName
    },
    {
      name: 'ReferenceImagePath',
      type: sql.NVarChar(500),
      value: referenceImagePath
    },
    {
      name: 'ViewType',
      type: sql.NVarChar(50),
      value: viewType
    },
    {
      name: 'IsActive',
      type: sql.Bit,
      value: isActive
    }
  ];

  await executeQuery(query, params);

  console.log(
    `Inserted MST_Component: ${componentName} | ${componentCode} | ${viewType}`
  );
}

module.exports = {
  insertComponentRecord
};