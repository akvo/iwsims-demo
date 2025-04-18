import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { View } from 'react-native';
import { useRoute } from '@react-navigation/native';
import { BaseLayout } from '../components';
import { FormNavigation, QuestionGroupList } from './support';
import QuestionGroup from './components/QuestionGroup';
import { transformForm, generateDataPointName } from './lib';
import { FormState } from '../store';
import { helpers } from '../lib';
import { SUBMISSION_TYPES } from '../lib/constants';

// TODO:: Allow other not supported yet
// TODO:: Repeat group not supported yet

const checkValuesBeforeCallback = ({ values, hiddenQIds = [] }) =>
  Object.keys(values)
    .map((key) => {
      // remove value where question is hidden
      if (hiddenQIds.includes(Number(key))) {
        return false;
      }
      // EOL remove value where question is hidden
      let value = values[key];
      if (typeof value === 'string') {
        value = value.trim();
      }
      // check array
      if (value && Array.isArray(value)) {
        const check = value.filter(
          (y) => typeof y !== 'undefined' && (y || Number.isNaN(Number(y))),
        );
        value = check.length ? check : null;
      }
      // check empty
      if (!value && value !== 0) {
        return false;
      }
      return { [key]: value };
    })
    .filter((v) => v)
    .reduce((res, current) => ({ ...res, ...current }), {});

const style = {
  flex: 1,
};

const FormContainer = ({ forms = {}, onSubmit, setShowDialogMenu }) => {
  const [activeGroup, setActiveGroup] = useState(0);
  const [showQuestionGroupList, setShowQuestionGroupList] = useState(false);
  const [isDefaultFilled, setIsDefaultFilled] = useState(false);
  const currentValues = FormState.useState((s) => s.currentValues);
  const cascades = FormState.useState((s) => s.cascades);
  const activeLang = FormState.useState((s) => s.lang);
  const route = useRoute();

  const dependantQuestions =
    forms?.question_group
      ?.flatMap((qg) => qg.question)
      .filter((q) => q?.dependency && q?.dependency?.length)
      ?.map((q) => ({ id: q.id, dependency: q.dependency })) || [];

  const formDefinition = transformForm(
    forms,
    currentValues,
    activeLang,
    route.params.submission_type,
  );
  const activeQuestions = formDefinition?.question_group?.flatMap((qg) => qg?.question);

  const hiddenQIds = useMemo(
    () =>
      forms?.question_group
        ?.flatMap((qg) => qg?.question)
        .map((q) => {
          const subTypeName = helpers.flipObject(SUBMISSION_TYPES)?.[route.params.submission_type];
          const hidden = q?.hidden ? q.hidden?.submission_type?.includes(subTypeName) : false;
          if (hidden) {
            return q.id;
          }
          return false;
        })
        .filter((x) => x),
    [forms, route.params.submission_type],
  );

  const currentGroup = useMemo(
    () => formDefinition?.question_group?.[activeGroup] || {},
    [formDefinition, activeGroup],
  );

  const handleOnSubmitForm = () => {
    const validValues = Object.keys(currentValues)
      .filter((qkey) => activeQuestions.map((q) => `${q.id}`).includes(qkey))
      .reduce((prev, current) => ({ [current]: currentValues[current], ...prev }), {});
    const results = checkValuesBeforeCallback({ values: validValues, hiddenQIds });
    if (onSubmit) {
      const { dpName, dpGeo } = generateDataPointName(forms, validValues, cascades);
      onSubmit({ name: dpName, geo: dpGeo, answers: results });
    }
  };

  const handleOnActiveGroup = (page) => {
    const group = formDefinition?.question_group?.[page];
    const currentPrefilled = group.question
      ?.filter((q) => q?.pre && q?.id)
      ?.filter(
        (q) => currentValues?.[q.id] === null || typeof currentValues?.[q.id] === 'undefined',
      )
      ?.map((q) => {
        const questionName = Object.keys(q.pre)?.[0];
        const findQuestion = activeQuestions.find((aq) => aq?.name === questionName);
        const prefillValue = q.pre?.[questionName]?.[currentValues?.[findQuestion?.id]];
        return { [q.id]: prefillValue };
      })
      ?.reduce((prev, current) => ({ ...prev, ...current }), {});
    if (Object.keys(currentPrefilled).length) {
      FormState.update((s) => {
        s.loading = true;
        s.currentValues = {
          ...s.currentValues,
          ...currentPrefilled,
        };
      });
      const interval = group?.question?.length || 0;
      setTimeout(() => {
        setActiveGroup(page);
        FormState.update((s) => {
          s.loading = false;
        });
      }, interval);
    } else {
      setActiveGroup(page);
    }
  };

  const handleOnDefaultValue = useCallback(() => {
    if (!isDefaultFilled) {
      setIsDefaultFilled(true);
      const defaultValues = activeQuestions
        .filter((aq) => aq?.default_value)
        .map((aq) => {
          const submissionType = route.params?.submission_type || SUBMISSION_TYPES.registration;
          const subTypeName = helpers.flipObject(SUBMISSION_TYPES)[submissionType];
          const defaultValue = aq?.default_value?.submission_type?.[subTypeName];
          if (['option', 'multiple_option'].includes(aq.type)) {
            return {
              [aq.id]: defaultValue ? [defaultValue] : [],
            };
          }
          return {
            [aq.id]: defaultValue || Number(defaultValue) === 0 ? defaultValue : '',
          };
        })
        .reduce((prev, current) => ({ ...prev, ...current }), {});
      if (Object.keys(defaultValues).length) {
        FormState.update((s) => {
          s.currentValues = { ...s.currentValues, ...defaultValues };
        });
      }
    }
  }, [activeQuestions, route.params, isDefaultFilled]);

  useEffect(() => {
    handleOnDefaultValue();
  }, [handleOnDefaultValue]);

  return (
    <>
      <BaseLayout.Content>
        <View style={style}>
          {!showQuestionGroupList ? (
            <QuestionGroup
              index={activeGroup}
              group={currentGroup}
              activeQuestions={activeQuestions}
              dependantQuestions={dependantQuestions}
            />
          ) : (
            <QuestionGroupList
              form={formDefinition}
              activeQuestionGroup={activeGroup}
              setActiveQuestionGroup={setActiveGroup}
              setShowQuestionGroupList={setShowQuestionGroupList}
            />
          )}
        </View>
      </BaseLayout.Content>
      <View>
        <FormNavigation
          currentGroup={currentGroup}
          onSubmit={handleOnSubmitForm}
          activeGroup={activeGroup}
          setActiveGroup={handleOnActiveGroup}
          totalGroup={formDefinition?.question_group?.length || 0}
          showQuestionGroupList={showQuestionGroupList}
          setShowQuestionGroupList={setShowQuestionGroupList}
          setShowDialogMenu={setShowDialogMenu}
        />
      </View>
    </>
  );
};

export default FormContainer;
