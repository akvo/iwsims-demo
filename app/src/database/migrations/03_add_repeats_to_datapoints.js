import sql from '../sql';

const tableName = 'datapoints';
const fieldName = 'repeats';
const fieldType = 'TEXT';

const up = (db) => sql.addNewColumn(db, tableName, fieldName, fieldType);

const down = (db) => sql.dropColumn(db, tableName, fieldName);

export { up, down };
