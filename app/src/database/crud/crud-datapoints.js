import sql from '../sql';

const selectDataPointById = async (db, { id }) => {
  const current = await sql.getFirstRow(db, 'datapoints', { id });
  if (!current) {
    return false;
  }
  return {
    ...current,
    json: JSON.parse(current.json.replace(/''/g, "'")),
  };
};

const dataPointsQuery = () => ({
  selectDataPointById,
  selectDataPointsByFormAndSubmitted: async (db, { form, submitted, user, uuid }) => {
    const uuidVal = uuid ? { uuid } : {};
    const userVal = user ? { user } : {};
    const columns = { form, submitted, ...userVal, ...uuidVal };
    const rows = sql.getFilteredRows(db, 'datapoints', { ...columns }, 'syncedAt', 'DESC', true);
    return rows;
  },
  selectSubmissionToSync: async (db) => {
    const submitted = 1;
    const rows = await sql.executeQuery(
      db,
      `
        SELECT
          datapoints.*,
          forms.formId,
          forms.json AS json_form
        FROM datapoints
        JOIN forms ON datapoints.form = forms.id
        WHERE datapoints.submitted = ${submitted} AND datapoints.syncedAt IS NULL
        ORDER BY datapoints.createdAt ASC
        LIMIT 1`,
    );
    return rows;
  },
  saveDataPoint: async (
    db,
    { uuid, form, user, name, geo, submitted, duration, json, repeats, syncedAt, administrationId },
  ) => {
    const repeatsVal = repeats ? { repeats } : {};
    const submittedAt = submitted ? { submittedAt: new Date().toISOString() } : {};
    const geoVal = geo ? { geo } : {};
    const uuidVal = uuid ? { uuid } : {};
    const syncedAtVal = syncedAt ? { syncedAt } : {};
    const admVal = administrationId ? { administrationId } : {};
    const res = await sql.insertRow(db, 'datapoints', {
      form,
      user,
      name,
      submitted,
      duration,
      createdAt: new Date().toISOString(),
      json: json ? JSON.stringify(json).replace(/'/g, "''") : null,
      ...geoVal,
      ...submittedAt,
      ...repeatsVal,
      ...uuidVal,
      ...syncedAtVal,
      ...admVal,
    });
    return res;
  },
  updateDataPoint: async (
    db,
    { id, name, geo, submitted, duration, submittedAt, syncedAt, json, repeats },
  ) => {
    const repeatsVal = repeats ? { repeats } : {};
    const submittedVal = submitted !== undefined ? { submitted } : {};
    const res = await sql.updateRow(
      db,
      'datapoints',
      { id },
      {
        name,
        geo,
        duration,
        syncedAt,
        submittedAt: submitted && !submittedAt ? new Date().toISOString() : submittedAt,
        json: json ? JSON.stringify(json).replace(/'/g, "''") : null,
        ...submittedVal,
        ...repeatsVal,
      },
    );
    return res;
  },
  saveToDraft: async (db, id) => {
    const res = await sql.updateRow(
      db,
      'datapoints',
      { id },
      {
        submitted: 0,
      },
    );
    return res;
  },
  getByUUID: async (db, { uuid }) => {
    const res = await sql.getFirstRow(db, 'datapoints', { uuid });
    return res;
  },
  updateByUUID: async (db, { uuid, json, syncedAt }) => {
    if (!json || typeof json !== 'object') {
      return false;
    }
    const res = await sql.updateRow(
      db,
      'datapoints',
      { uuid },
      {
        json: JSON.stringify(json).replace(/'/g, "''"),
        syncedAt: syncedAt || new Date().toISOString(),
      },
    );
    return res;
  },
  countSavedDatapoints: async (db, { form }) => {
    const rows = await sql.executeQuery(
      db,
      `
        SELECT
          COUNT(*) AS total
        FROM datapoints
        WHERE form = ? AND submitted = 0`,
      [form],
    );
    return rows[0]?.total || 0;
  },
});

const crudDataPoints = dataPointsQuery();

export default crudDataPoints;
