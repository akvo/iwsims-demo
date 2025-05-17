/* eslint-disable import/prefer-default-export */

export const SYNC_FORM_VERSION_TASK_NAME = 'sync-form-version';

export const SYNC_FORM_SUBMISSION_TASK_NAME = 'sync-form-submission';

export const SYNC_STATUS = {
  on_progress: 1,
  re_sync: 2,
  success: 3,
  failed: 4,
};

export const SUBMISSION_TYPES = {
  registration: 1,
  monitoring: 2,
};

export const DATABASE_NAME = 'app.db';

export const DATABASE_VERSION = 3;

export const QUESTION_TYPES = {
  text: 'text',
  number: 'number',
  date: 'date',
  photo: 'photo',
  geo: 'geo',
  option: 'option',
  multiple_option: 'multiple_option',
  cascade: 'cascade',
  autofield: 'autofield',
  attachment: 'attachment',
  signature: 'signature',
};
