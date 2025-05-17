/**
 * Creates a table if it does not already exist.
 *
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to create.
 * @param {Object} fields - An object representing the column names and their corresponding data types.
 * @returns {Promise<void>} A promise that resolves when the table has been created.
 */
const createTable = async (db, table, fields) => {
  const columns = Object.entries(fields)
    .map(([name, type]) => `${name} ${type}`)
    .join(', ');
  await db.execAsync(`
    CREATE TABLE IF NOT EXISTS ${table} (
      ${columns}
    );
  `);
  const res = await db.getFirstAsync(`PRAGMA table_info(${table})`);
  return res;
};

/**
 * Updates a row in the specified table in the database.
 *
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to update the row in.
 * @param {Object} [conditions={ id: 1 }] - An object representing the conditions for identifying the row to update.
 * @param {Object} values - An object representing the column names and their corresponding values to be updated.
 * @returns {Promise<void>} A promise that resolves when the row has been updated.
 */
const updateRow = async (db, table, conditions = { id: 1 }, values = {}) => {
  const setClause = Object.keys(values)
    .map((key) => `${key} = ?`)
    .join(', ');
  const whereClause = Object.keys(conditions)
    .map((key) => `${key} = ?`)
    .join(' AND ');
  const params = [...Object.values(values), ...Object.values(conditions)];
  await db.runAsync(`UPDATE ${table} SET ${setClause} WHERE ${whereClause}`, ...params);
};

/**
 * Deletes a row from the specified table in the database.
 *
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to delete the row from.
 * @param {number} id - The ID of the row to delete.
 * @returns {Promise<void>} A promise that resolves when the row has been deleted.
 */
const deleteRow = async (db, table, id) => {
  await db.runAsync(`DELETE FROM ${table} WHERE id = ?`, id);
};

/**
 * Retrieves the first row from the specified table in the database with optional conditions.
 *
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to retrieve the first row from.
 * @param {Object} [conditions={}] - An object representing the conditions for filtering rows (optional).
 * @returns {Promise<Object>} A promise that resolves to the first row in the table.
 */
const getFirstRow = async (db, table, conditions = {}) => {
  const whereClause = Object.keys(conditions).length
    ? Object.keys(conditions)
        .map((key) => (conditions[key] === null ? `${key} IS NULL` : `${key} = ?`))
        .join(' AND ')
    : false;
  const params = Object.values(conditions);
  const query = `
    SELECT * FROM ${table}
    ${whereClause ? `WHERE ${whereClause}` : ''}
    LIMIT 1;
  `;
  const firstRow = await db.getFirstAsync(query, ...params);
  return firstRow;
};

/**
 * Inserts a row into the specified table in the database.
 *
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to insert the row into.
 * @param {Object} values - An object representing the column names and their corresponding values to be inserted.
 * @returns {Promise<void>} A promise that resolves when the row has been inserted.
 */
const insertRow = async (db, table, values) => {
  const columns = Object.keys(values).join(', ');
  const placeholders = Object.keys(values)
    .map(() => '?')
    .join(', ');
  const params = Object.values(values);
  const res = await db.runAsync(
    `INSERT INTO ${table} (${columns}) VALUES (${placeholders})`,
    ...params,
  );
  return res?.lastInsertRowId;
};

/**
 * Retrieves all rows from the specified table in the database.
 *
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to retrieve all rows from.
 * @returns {Promise<Array>} A promise that resolves to an array of all rows in the table.
 */
const getEachRow = async (db, table) => {
  const rows = await db.getAllAsync(`SELECT * FROM ${table}`);
  return rows;
};

/**
 * Retrieves filtered rows from a specified table in the database.
 *
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to query.
 * @param {Object} conditions - An object representing the conditions for filtering rows.
 * @param {string} [orderBy=null] - The column name to order the results by (optional).
 * @param {string} [order='ASC'] - The order direction, either 'ASC' for ascending or 'DESC' for descending (optional).
 * @param {boolean} [collateNoCase=false] - Whether to use COLLATE NOCASE for case-insensitive matching (optional).
 * @returns {Promise<Array>} A promise that resolves to an array of filtered rows.
 */
const getFilteredRows = async (
  db,
  table,
  conditions,
  orderBy = null,
  order = 'ASC',
  collateNoCase = false,
) => {
  const whereClause = Object.keys(conditions)
    .map((key) => (conditions[key] === null ? `${key} IS NULL` : `${key} = ?`))
    .join(' AND ');
  const params = Object.values(conditions);
  const orderClause = orderBy ? `ORDER BY ${orderBy} ${order}` : '';
  const collateClause = collateNoCase ? 'COLLATE NOCASE' : '';
  const query = `
    SELECT * FROM ${table}
    WHERE ${whereClause} ${collateClause}
    ${orderClause};
  `;
  const rows = await db.getAllAsync(query, ...params);
  return rows;
};

/**
 * Executes a custom query on the database.
 *
 * @param {Object} db - The database connection object.
 * @param {string} query - The SQL query to execute.
 * @param {Array} [params=[]] - The parameters to pass to the query (optional).
 * @returns {Promise<Array>} A promise that resolves to the result of the query.
 */
const executeQuery = async (db, query, params = []) => {
  const result = await db.getAllAsync(query, ...params);
  return result;
};

/**
 * Drop a table from the database.
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to drop.
 * @returns {Promise<void>} A promise that resolves when the table has been dropped.
 */
const dropTable = async (db, table) => {
  await db.execAsync(`DROP TABLE IF EXISTS ${table}`);
};

/**
 * Truncate a table from the database and check cascade.
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to truncate.
 * @returns {Promise<void>} A promise that resolves when the table has been truncated.
 */
const truncateTable = async (db, table) => {
  // Disable foreign key constraints
  await db.execAsync('PRAGMA foreign_keys = OFF');

  // Truncate the table
  await db.execAsync(`DELETE FROM ${table}`);

  // Enable foreign key constraints
  await db.execAsync('PRAGMA foreign_keys = ON');
};

/**
 * add a new column to a table if it does not already exist
 * @param {Object} db - The datdabase connection object.
 * @param {string} table - the name of the table to add the column to.
 * @param {string} columnName - the name of the column to add.
 * @param {string} columnType - the type of the column to add.
 */
const addNewColumn = async (db, table, columnName, columnType) => {
  // Check if the column already exists
  const rows = await db.getAllAsync(`PRAGMA table_info(${table})`);
  const existingColumn = rows.find((row) => row?.name === columnName);

  if (!existingColumn) {
    // Add the new column to the table
    await db.execAsync(`ALTER TABLE ${table} ADD COLUMN ${columnName} ${columnType}`);
  }
};
/**
 * Drop a column to table if it exists
 * @param {Object} db - The database connection object.
 * @param {string} table - The name of the table to drop the column from.
 * @param {string} columnName - The name of the column to drop.
 * @returns {Promise<void>} A promise that resolves when the column has been dropped.
 * @throws {Error} If the column does not exist or if dropping the column fails.
 * @description SQLite does not support dropping columns directly, so this function creates a new table without the column,
 * copies the data over, drops the old table, and renames the new table to the original name.
 * This is a workaround for SQLite's limitations.
 */
const dropColumn = async (db, table, columnName) => {
  // Check if the column already exists
  const rows = await db.getAllAsync(`PRAGMA table_info(${table})`);
  const existingColumn = rows.find((row) => row?.name === columnName);
  // If the column does not exist, return early
  if (!existingColumn) {
    return;
  }

  if (existingColumn) {
    // SQLite does not support dropping columns directly, so we need to create a new table without the column
    // and copy the data over
    const tempTable = `${table}_temp`;
    await db.execAsync(`CREATE TABLE ${tempTable} AS SELECT * FROM ${table} WHERE 1=0;`);
    const columns = await db.getAllAsync(`PRAGMA table_info(${table})`);
    const columnNames = columns
      .filter((col) => col.name !== columnName)
      .map((col) => col.name)
      .join(', ');
    await db.execAsync(
      `INSERT INTO ${tempTable} (${columnNames}) SELECT ${columnNames} FROM ${table};`,
    );
    await db.execAsync(`DROP TABLE ${table};`);
    await db.execAsync(`ALTER TABLE ${tempTable} RENAME TO ${table};`);
  }
};

const sql = {
  createTable,
  updateRow,
  deleteRow,
  getFirstRow,
  insertRow,
  getEachRow,
  getFilteredRows,
  executeQuery,
  dropTable,
  truncateTable,
  addNewColumn,
  dropColumn,
};

export default sql;
