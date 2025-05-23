/**
 * @module migrations/03_add_repeats_to_datapoints
 * @description Migration script to add a new column 'repeats' to the 'datapoints' table.
 * @see {@link https://www.sqlite.org/lang_altertable.html#altertableaddcolumn} for SQLite documentation on adding columns.
 */
import sql from '../sql';

const tableName = 'datapoints';
const fieldName = 'repeats';
const fieldType = 'TEXT';

const up = (db) => sql.addNewColumn(db, tableName, fieldName, fieldType);

const down = (db) => sql.dropColumn(db, tableName, fieldName);

export { up, down };
