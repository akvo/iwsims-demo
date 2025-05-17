import * as BackgroundFetch from 'expo-background-fetch';
import * as TaskManager from 'expo-task-manager';
import * as Network from 'expo-network';
import * as Sentry from '@sentry/react-native';
import * as SQLite from 'expo-sqlite';
import api from './api';
import { crudForms, crudDataPoints, crudUsers, crudConfig } from '../database/crud';
import notification from './notification';
import crudJobs from '../database/crud/crud-jobs';
import { UIState } from '../store';
import {
  DATABASE_NAME,
  QUESTION_TYPES,
  SYNC_FORM_SUBMISSION_TASK_NAME,
  SYNC_FORM_VERSION_TASK_NAME,
  SYNC_STATUS,
} from './constants';
import MIME_TYPES from './mime_types';

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

const handleOnUploadFiles = async (
  data,
  apiURL = '/images',
  questionTypes = [QUESTION_TYPES.photo],
) => {
  // Extract files from submissions
  const allFiles = data.reduce((files, d) => {
    try {
      const answers = JSON.parse(d.json);
      const questions = JSON.parse(d.json_form)?.question_group?.flatMap((qg) => qg.question) || [];
      const questionFiles = questions.filter((q) => questionTypes.includes(q.type));
      if (!questionFiles.length) return files;

      Object.entries(answers).forEach(([key, value]) => {
        const [questionId] = key.split('-');
        const question = questionFiles.find((q) => `${q.id}` === questionId);
        if (question && value?.startsWith('file://')) {
          files.push({ id: key, value, dataID: d.id });
        }
      });
      return files;
    } catch {
      return files;
    }
  }, []);

  if (!allFiles.length) return [];

  // Prepare file uploads
  const uploads = allFiles.map((f) => {
    const extension = f.value.split('.').pop()?.toLowerCase();
    const fileType = MIME_TYPES[extension] || 'application/octet-stream';
    const formData = new FormData();
    formData.append('file', {
      uri: f.value,
      name: `file_${f.id}_${f.dataID}.${extension}`,
      type: fileType,
    });
    return api.post(apiURL, formData, {
      headers: {
        Accept: 'application/json',
        'Content-Type': 'multipart/form-data',
      },
    });
  });

  // Upload all and return merged results
  const results = await Promise.allSettled(uploads);
  const responses = results
    .filter((result) => result.status === 'fulfilled')
    .map((result) => result.value);
  return responses.map((res, i) => ({ ...allFiles[i], ...res.data }));
};

const syncFormSubmission = async (activeJob = {}) => {
  const db = await SQLite.openDatabaseAsync(DATABASE_NAME, {
    useNewConnection: true,
  });
  const { isConnected } = await Network.getNetworkStateAsync();
  if (!isConnected) {
    return BackgroundFetch.BackgroundFetchResult.NoData;
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
    const photos = await handleOnUploadFiles(data, '/images', [QUESTION_TYPES.photo]);
    const attachments = await handleOnUploadFiles(data, '/attachments', [
      QUESTION_TYPES.attachment,
    ]);
    const syncProcess = data.map(async (d) => {
      try {
        const geo = d.geo ? d.geo.split('|')?.map((x) => parseFloat(x)) : [];
        const answerValues = JSON.parse(d.json.replace(/''/g, "'"));

        // Add photos and attachments to answers
        [...photos, ...attachments]
          .filter((file) => file?.dataID === d.id)
          .forEach((file) => {
            answerValues[file?.id] = file?.file;
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

        // Handle UUID
        const uuidv4Regex =
          /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
        if (uuidv4Regex.test(d?.uuid)) {
          syncData.uuid = d.uuid;
        } else if (uuidv4Regex.test(activeJob?.info)) {
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
          success: true,
        };
      } catch (error) {
        Sentry.captureException(error);
        // Mark datapoint as not submitted
        await crudDataPoints.saveToDraft(db, d.id);
        return {
          datapoint: d.id,
          status: 'error',
          message: error.message,
          success: false,
        };
      }
    });

    const results = await Promise.allSettled(syncProcess);
    const hasFailures = results.some(
      (result) =>
        result.status === 'rejected' ||
        (result.status === 'fulfilled' && result.value?.success === false),
    );
    if (hasFailures) {
      // Delete job on any failure
      if (activeJob?.id) {
        await crudJobs.deleteJob(db, activeJob.id);
      }
      UIState.update((s) => {
        s.statusBar = {
          type: SYNC_STATUS.failed,
          bgColor: '#ec003f',
          icon: 'alert-sharp',
        };
      });
    } else {
      // All succeeded
      UIState.update((s) => {
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

      if (activeJob?.id) {
        // delete the job when it's succeed
        await crudJobs.deleteJob(db, activeJob.id);
      }
    }

    await db.closeAsync();
    return BackgroundFetch.BackgroundFetchResult.NewData;
  } catch (error) {
    Sentry.captureMessage(`[background-task] syncFormSubmission failed`);
    Sentry.captureException(error);

    if (activeJob?.id) {
      // Delete job immediately on error
      await crudJobs.deleteJob(db, activeJob.id);
    }

    await db.closeAsync();
    return Promise.reject(
      new Error({ errorCode: error?.response?.status, message: error?.message }),
    );
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
