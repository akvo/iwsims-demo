import { useCallback, useEffect } from 'react';
import * as Network from 'expo-network';
import { useSQLiteContext } from 'expo-sqlite';
import { BuildParamsState, DatapointSyncState, UIState } from '../store';
import { backgroundTask } from '../lib';
import crudJobs, {
  jobStatus,
  MAX_ATTEMPT,
  SYNC_DATAPOINT_JOB_NAME,
} from '../database/crud/crud-jobs';
import { crudConfig, crudDataPoints } from '../database/crud';
import { downloadDatapointsJson, fetchDatapoints } from '../lib/sync-datapoints';
import { SYNC_FORM_SUBMISSION_TASK_NAME, SYNC_STATUS } from '../lib/constants';
/**
 * This sync only works in the foreground service
 */
const SyncService = () => {
  const isOnline = UIState.useState((s) => s.online);
  const syncInterval = BuildParamsState.useState((s) => s.dataSyncInterval);
  const syncInSecond = parseInt(syncInterval, 10) * 1000;
  const db = useSQLiteContext();

  const onSync = useCallback(async () => {
    const pendingToSync = await crudDataPoints.selectSubmissionToSync(db);
    const activeJob = await crudJobs.getActiveJob(db, SYNC_FORM_SUBMISSION_TASK_NAME);
    const settings = await crudConfig.getConfig(db);

    const { type: networkType } = await Network.getNetworkStateAsync();
    if (settings?.syncWifiOnly && networkType !== Network.NetworkStateType.WIFI) {
      return;
    }

    if (activeJob?.status === jobStatus.ON_PROGRESS) {
      if (activeJob.attempt < MAX_ATTEMPT) {
        /**
         * Job is still in progress,
         * but we still have pending items; then increase the attempt value.
         */
        await crudJobs.updateJob(db, activeJob.id, {
          attempt: activeJob.attempt + 1,
        });
      }

      if (activeJob.attempt === MAX_ATTEMPT) {
        /**
         * If the status is still IN PROGRESS and has reached the maximum attempts,
         * set it to PENDING when there are still pending sync items,
         * delete the job when it's finish and there are no pending items.
         */
        if (pendingToSync) {
          UIState.update((s) => {
            s.statusBar = {
              type: SYNC_STATUS.re_sync,
              bgColor: '#d97706',
              icon: 'repeat',
            };
          });
          await crudJobs.updateJob(db, activeJob.id, {
            status: jobStatus.PENDING,
            attempt: 0, // RESET attempt to 0
          });
        } else {
          UIState.update((s) => {
            s.statusBar = {
              type: SYNC_STATUS.success,
              bgColor: '#16a34a',
              icon: 'checkmark-done',
            };
          });
          await crudJobs.deleteJob(db, activeJob.id);
        }
      }
    }

    if (
      activeJob?.status === jobStatus.PENDING ||
      (activeJob?.status === jobStatus.FAILED && activeJob?.attempt <= MAX_ATTEMPT)
    ) {
      UIState.update((s) => {
        s.statusBar = {
          type: SYNC_STATUS.on_progress,
          bgColor: '#2563eb',
          icon: 'sync',
        };
      });
      await crudJobs.updateJob(db, activeJob.id, {
        status: jobStatus.ON_PROGRESS,
      });
      await backgroundTask.syncFormSubmission(activeJob);
    }
  }, [db]);

  useEffect(() => {
    if (!syncInSecond || !isOnline) {
      return;
    }
    const syncTimer = setInterval(() => {
      // Perform sync operation
      onSync();
    }, syncInSecond);

    // eslint-disable-next-line consistent-return
    return () =>
      // Clear the interval when the component unmounts
      clearInterval(syncTimer);
  }, [syncInSecond, isOnline, onSync]);

  const onSyncDataPoint = useCallback(async () => {
    const activeJob = await crudJobs.getActiveJob(db, SYNC_DATAPOINT_JOB_NAME);

    DatapointSyncState.update((s) => {
      s.added = false;
      s.inProgress = !!activeJob;
    });

    if (activeJob && activeJob.status === jobStatus.PENDING && activeJob.attempt < MAX_ATTEMPT) {
      await crudJobs.updateJob(db, activeJob.id, {
        status: jobStatus.ON_PROGRESS,
      });

      try {
        const monitoringRes = await fetchDatapoints();
        const apiURLs = monitoringRes.map(
          ({
            url,
            form_id: formId,
            administration_id: administrationId,
            last_updated: lastUpdated,
          }) => ({
            url,
            formId,
            administrationId,
            lastUpdated,
          }),
        );

        await Promise.all(apiURLs.map((u) => downloadDatapointsJson(db, u, activeJob.user)));
        await crudJobs.deleteJob(db, activeJob.id);

        DatapointSyncState.update((s) => {
          s.inProgress = false;
        });
      } catch (error) {
        DatapointSyncState.update((s) => {
          s.added = true;
        });
        await crudJobs.updateJob(db, activeJob.id, {
          status: jobStatus.PENDING,
          attempt: activeJob.attempt + 1,
          info: String(error),
        });
      }
    }

    if (activeJob && activeJob.status === jobStatus.PENDING && activeJob.attempt === MAX_ATTEMPT) {
      await crudJobs.deleteJob(db, activeJob.id);
      DatapointSyncState.update((s) => {
        s.inProgress = false;
      });
    }
  }, [db]);

  useEffect(() => {
    const unsubsDataSync = DatapointSyncState.subscribe(
      (s) => s.added,
      (added) => {
        if (added) {
          onSyncDataPoint();
        }
      },
    );

    return () => {
      unsubsDataSync();
    };
  }, [onSyncDataPoint]);

  return null; // This is a service component, no rendering is needed
};

export default SyncService;
