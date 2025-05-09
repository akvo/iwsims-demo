import * as SQLite from 'expo-sqlite';

import { crudMonitoring } from '../database/crud';
import { DatapointSyncState } from '../store';
import api from './api';
import { DATABASE_NAME } from './constants';

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

export const downloadDatapointsJson = async ({ formId, administrationId, url, lastUpdated }) => {
  try {
    const db = await SQLite.openDatabaseAsync(DATABASE_NAME, {
      useNewConnection: true,
    });
    const response = await api.get(url);
    if (response.status === 200) {
      const jsonData = response.data;
      await crudMonitoring.syncForm(db, {
        formId,
        administrationId,
        lastUpdated,
        formJSON: jsonData,
      });
      await db.closeAsync();
    }
  } catch (error) {
    Promise.reject(error);
  }
};
