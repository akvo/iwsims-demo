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
  selectDataPointsByFormAndSubmitted: async (db, { form, submitted, user }) => {
    const columns = user ? { form, submitted, user } : { form, submitted };
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
    { form, user, name, geo, submitted, duration, json, submissionType, repeats },
  ) => {
    const repeatsVal = repeats ? { repeats } : {};
    const submittedAt = submitted ? { submittedAt: new Date().toISOString() } : {};
    const geoVal = geo ? { geo } : {};
    const res = await sql.insertRow(db, 'datapoints', {
      form,
      user,
      name,
      ...geoVal,
      submitted,
      duration,
      createdAt: new Date().toISOString(),
      json: json ? JSON.stringify(json).replace(/'/g, "''") : null,
      submission_type: submissionType,
      ...submittedAt,
      ...repeatsVal,
    });
    return res;
  },
  updateDataPoint: async (
    db,
    { id, name, geo, submitted, duration, submittedAt, syncedAt, json, submissionType, repeats },
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
        submission_type: submissionType,
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
});

const crudDataPoints = dataPointsQuery();

export default crudDataPoints;
