import * as BackgroundFetch from 'expo-background-fetch';
import * as TaskManager from 'expo-task-manager';
import * as Network from 'expo-network';
import * as Sentry from '@sentry/react-native';
import * as SQLite from 'expo-sqlite';
import api from './api';
import { crudForms, crudDataPoints, crudUsers, crudConfig } from '../database/crud';
import notification from './notification';
import crudJobs, { jobStatus, MAX_ATTEMPT } from '../database/crud/crud-jobs';
import { UIState } from '../store';
import {
  DATABASE_NAME,
  SYNC_FORM_SUBMISSION_TASK_NAME,
  SYNC_FORM_VERSION_TASK_NAME,
  SYNC_STATUS,
} from './constants';

const syncFormVersion = async ({
  showNotificationOnly = true,
  sendPushNotification = () => {},
}) => {
  const db = await SQLite.openDatabaseAsync(DATABASE_NAME, {
    useNewConnection: true,
  });
  const { isConnected } = await Network.getNetworkStateAsync();
  if (!isConnected) {
    return;
  }
  try {
    // find last session
    const session = await crudUsers.getActiveUser(db);
    if (!session) {
      return;
    }
    api.post('/auth', { code: session.password }).then(async (res) => {
      const { data } = res;
      const promises = data.formsUrl.map(async (form) => {
        const formExist = await crudForms.selectFormByIdAndVersion(db, { ...form });
        if (formExist) {
          return false;
        }
        if (showNotificationOnly) {
          return { id: form.id, version: form.version };
        }
        const formRes = await api.get(form.url);
        // update previous form latest value to 0
        await crudForms.updateForm(db, { ...form });
        const savedForm = await crudForms.addForm(db, {
          ...form,
          userId: session?.id,
          formJSON: formRes?.data,
        });
        return savedForm;
      });
      Promise.all(promises).then((r) => {
        const exist = r.filter((x) => x);
        if (!exist.length || !showNotificationOnly) {
          return;
        }
        sendPushNotification();
      });
      await db.closeAsync();
    });
  } catch (err) {
    Sentry.captureMessage('[background-task] syncFormVersion failed');
    Sentry.captureException(err);
  }
};

const registerBackgroundTask = async (TASK_NAME, settingsValue = null) => {
  try {
    const db = await SQLite.openDatabaseAsync(DATABASE_NAME, {
      useNewConnection: true,
    });
    const config = await crudConfig.getConfig(db);
    const syncInterval = settingsValue || parseInt(config?.syncInterval, 10) || 3600;
    const res = await BackgroundFetch.registerTaskAsync(TASK_NAME, {
      minimumInterval: syncInterval,
      stopOnTerminate: false, // android only,
      startOnBoot: true, // android only
    });
    await db.closeAsync();
    return res;
  } catch (err) {
    return Promise.reject(err);
  }
};

const unregisterBackgroundTask = async (TASK_NAME) => {
  try {
    const res = await BackgroundFetch.unregisterTaskAsync(TASK_NAME);
    return res;
  } catch (err) {
    return Promise.reject(err);
  }
};

const backgroundTaskStatus = async (TASK_NAME) => {
  await BackgroundFetch.getStatusAsync();
  await TaskManager.isTaskRegisteredAsync(TASK_NAME);
};

const handleOnUploadPhotos = async (data) => {
  const AllPhotos = data?.flatMap((d) => {
    const answers = JSON.parse(d.json);
    const questions = JSON.parse(d.json_form)?.question_group?.flatMap((qg) => qg.question) || [];
    const photos = questions
      .filter((q) => q.type === 'photo')
      .map((q) => ({ id: q.id, value: answers?.[q.id], dataID: d.id }))
      .filter((p) => p.value);
    return photos;
  });

  if (AllPhotos?.length) {
    const uploads = AllPhotos.map((p) => {
      const fileType = p.value.split('.').slice(-1)?.[0];
      const formData = new FormData();
      formData.append('file', {
        uri: p.value,
        name: `photo_${p.id}_${p.dataID}.${fileType}`,
        type: `image/${fileType}`,
      });
      return api.post('/images', formData, {
        headers: {
          Accept: 'application/json',
          'Content-Type': 'multipart/form-data',
        },
      });
    });

    const responses = await Promise.allSettled(uploads);
    const results = responses
      .filter(({ status }) => status === 'fulfilled')
      .map(({ value: resValue }) => {
        const { data: fileData } = resValue;
        const findPhoto =
          AllPhotos.find((ap) => fileData?.file?.includes(`${ap.id}_${ap.dataID}`)) || {};
        return {
          ...fileData,
          ...findPhoto,
        };
      })
      .filter((d) => d);
    return results;
  }
  return [];
};

const syncFormSubmission = async (activeJob = {}) => {
  const db = await SQLite.openDatabaseAsync(DATABASE_NAME, {
    useNewConnection: true,
  });
  const { isConnected } = await Network.getNetworkStateAsync();
  if (!isConnected) {
    return;
  }
  try {
    let sendNotification = false;
    // get token
    const session = await crudUsers.getActiveUser(db);
    // set token
    api.setToken(session.token);
    // get all datapoints to sync
    const data = await crudDataPoints.selectSubmissionToSync(db);
    /**
     * Upload all photo of questions first
     */
    const photos = await handleOnUploadPhotos(data);
    const syncProcess = data.map(async (d) => {
      const geo = d.geo ? d.geo.split('|')?.map((x) => parseFloat(x)) : [];

      const answerValues = JSON.parse(d.json.replace(/''/g, "'"));
      photos
        ?.filter((pt) => pt?.dataID === d.id)
        ?.forEach((pt) => {
          answerValues[pt?.id] = pt?.file;
        });
      const syncData = {
        formId: d.formId,
        name: d.name,
        duration: Math.round(d.duration),
        submittedAt: d.submittedAt,
        submitter: session.name,
        geo,
        answers: answerValues,
        submission_type: d.submission_type,
      };
      const uuidv4Regex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
      if (uuidv4Regex.test(d?.uuid)) {
        syncData.uuid = d.uuid;
      }
      if (!syncData?.uuid && uuidv4Regex.test(activeJob?.info)) {
        syncData.uuid = activeJob.info;
      }
      // sync data point
      const res = await api.post('/sync', syncData);
      if (res.status === 200) {
        // update data point
        await crudDataPoints.updateDataPoint(db, {
          ...d,
          submissionType: d?.submission_type,
          syncedAt: new Date().toISOString(),
        });
        sendNotification = true;
      }
      return {
        datapoint: d.id,
        status: res.status,
      };
    });
    await Promise.all(syncProcess);

    UIState.update((s) => {
      // TODO: rename isManualSynced w/ isSynced to refresh the Homepage stats
      s.isManualSynced = true;
      s.statusBar = {
        type: SYNC_STATUS.success,
        bgColor: '#16a34a',
        icon: 'checkmark-done',
      };
    });

    if (sendNotification) {
      notification.sendPushNotification('sync-form-submission');
    }
    sendNotification = false;
    if (activeJob?.id) {
      // delete the job when it's succeed
      await crudJobs.deleteJob(db, activeJob.id);
    }
    await db.closeAsync();
  } catch (error) {
    Sentry.captureMessage(`[background-task] syncFormSubmission failed`);
    Sentry.captureException(error);
    const { status: errorCode } = error?.response || {};
    if (activeJob?.id) {
      const updatePayload =
        activeJob.attempt < MAX_ATTEMPT
          ? { status: jobStatus.FAILED, attempt: activeJob.attempt + 1 }
          : { status: jobStatus.ON_PROGRESS, info: String(error) };
      crudJobs.updateJob(db, activeJob.id, updatePayload);
    }
    Promise.reject(new Error({ errorCode, message: error?.message }));
  }
};

const backgroundTaskHandler = () => ({
  syncFormVersion,
  registerBackgroundTask,
  unregisterBackgroundTask,
  backgroundTaskStatus,
  syncFormSubmission,
});

const backgroundTask = backgroundTaskHandler();

export const defineSyncFormVersionTask = () =>
  TaskManager.defineTask(SYNC_FORM_VERSION_TASK_NAME, async () => {
    try {
      await syncFormVersion({
        sendPushNotification: notification.sendPushNotification,
        showNotificationOnly: true,
      });
      return BackgroundFetch.BackgroundFetchResult.NewData;
    } catch (err) {
      Sentry.captureMessage(`[${SYNC_FORM_VERSION_TASK_NAME}] defineSyncFormVersionTask failed`);
      Sentry.captureException(err);
      return BackgroundFetch.Result.Failed;
    }
  });

export const defineSyncFormSubmissionTask = () => {
  TaskManager.defineTask(SYNC_FORM_SUBMISSION_TASK_NAME, async () => {
    try {
      await syncFormSubmission();
      return BackgroundFetch.BackgroundFetchResult.NewData;
    } catch (err) {
      Sentry.captureMessage(
        `[${SYNC_FORM_SUBMISSION_TASK_NAME}] defineSyncFormSubmissionTask failed`,
      );
      Sentry.captureException(err);
      return BackgroundFetch.Result.Failed;
    }
  });
};

export default backgroundTask;
