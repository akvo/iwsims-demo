import { crudDataPoints, crudForms } from '../database/crud';
import { DatapointSyncState } from '../store';
import api from './api';

export const fetchDatapoints = async (pageNumber = 1) => {
  try {
    const { data: apiData } = await api.get(`/datapoint-list?page=${pageNumber}`);
    const { data, total_page: totalPage, current: page } = apiData;
    DatapointSyncState.update((s) => {
      s.progress = (page / totalPage) * 100;
    });
    if (page < totalPage) {
      return data.concat(await fetchDatapoints(page + 1));
    }
    return data;
  } catch (error) {
    return Promise.reject(error);
  }
};

export const downloadDatapointsJson = async (
  db,
  { formId, administrationId, url, lastUpdated },
  user,
) => {
  try {
    const response = await api.get(url);
    if (response.status === 200) {
      const jsonData = response.data;
      const { uuid, datapoint_name: name, geolocation: geo, answers } = jsonData || {};
      const form = await crudForms.getByFormId(db, { formId });
      const isExists = await crudDataPoints.getByUUID(db, { uuid });
      if (isExists) {
        await crudDataPoints.updateByUUID(db, {
          uuid,
          json: answers,
          syncedAt: lastUpdated,
        });
      } else {
        await crudDataPoints.saveDataPoint(db, {
          uuid,
          user,
          geo,
          name,
          administrationId,
          form: form?.id,
          submitted: 1,
          duration: 0,
          createdAt: new Date().toISOString(),
          json: answers,
          syncedAt: lastUpdated,
        });
      }
    }
  } catch (error) {
    Promise.reject(error);
  }
};
