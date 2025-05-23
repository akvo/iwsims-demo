import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { ActivityIndicator, FlatList, StyleSheet } from 'react-native';
import { Button, ListItem } from '@rneui/themed';
import { useSQLiteContext } from 'expo-sqlite';
import { BaseLayout } from '../../components';
import { FormState, UIState } from '../../store';
import { helpers, i18n } from '../../lib';
import { crudMonitoring } from '../../database/crud';
import { transformMonitoringData } from '../../form/lib';
import { SUBMISSION_TYPES } from '../../lib/constants';

const UpdateForm = ({ navigation, route }) => {
  const params = route?.params || null;
  const [search, setSearch] = useState('');
  const [forms, setForms] = useState([]);
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const selectedForm = FormState.useState((s) => s.form);
  const db = useSQLiteContext();

  const formId = params?.formId;
  const loadMore = useMemo(() => forms.length < total, [forms, total]);
  const subTitle = useMemo(() => {
    const submissionType = route.params?.submission_type || SUBMISSION_TYPES.registration;
    return helpers.flipObject(SUBMISSION_TYPES)[submissionType]?.toUpperCase();
  }, [route.params?.submission_type]);

  const handleUpdateForm = (item) => {
    const { currentValues, prevAdmAnswer } = transformMonitoringData(
      selectedForm,
      JSON.parse(item.json.replace(/''/g, "'")),
    );
    const activeForm = JSON.parse(selectedForm?.json);
    const repeats = {};
    // Loop over all repeatable question groups
    activeForm?.question_group?.forEach((group) => {
      if (group?.repeatable) {
        // For each question in the group, count how many keys in currentValues contain the question id
        const repeatCount =
          group.question.reduce((maxCount, q) => {
            const count = Object.keys(currentValues).filter((key) => {
              const [questionId] = key.split('-');
              return questionId === `${q.id}`;
            }).length;
            return Math.max(maxCount, count);
          }, 0) || 1; // default to 1 if no repeat count found
        repeats[group.name] = Array.from({ length: repeatCount }, (_, i) => i);
      }
    });
    FormState.update((s) => {
      s.repeats = repeats;
      s.currentValues = currentValues;
      s.prevAdmAnswer = prevAdmAnswer;
    });
    navigation.navigate('FormPage', {
      ...route.params,
      newSubmission: true,
      uuid: item?.uuid,
    });
  };

  const handleOnSearch = (keyword) => {
    if (keyword?.trim()?.length === 0) {
      setForms([]);
    }
    setSearch(keyword);
    if (!isLoading) {
      setPage(0);
      setIsLoading(true);
    }
  };

  const fetchTotal = useCallback(async () => {
    const totalPage = await crudMonitoring.getTotal(db, formId, search);
    setTotal(totalPage);
  }, [db, formId, search]);

  useEffect(() => {
    fetchTotal();
  }, [fetchTotal]);

  const fetchData = useCallback(async () => {
    if (isLoading) {
      setIsLoading(false);
      const moreForms = await crudMonitoring.getFormsPaginated(db, {
        formId,
        search: search.trim(),
        limit: 10,
        offset: page,
      });
      if (search) {
        setForms(moreForms);
      } else {
        setForms(forms.concat(moreForms));
      }
    }
  }, [db, isLoading, forms, formId, page, search]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const renderItem = ({ item }) => (
    <ListItem
      bottomDivider
      containerStyle={styles.listItemContainer}
      onPress={() => handleUpdateForm(item)}
    >
      <ListItem.Content>
        <ListItem.Title>{item.name}</ListItem.Title>
      </ListItem.Content>
    </ListItem>
  );

  return (
    <BaseLayout
      title={total ? `${route?.params?.name} (${total})` : route?.params?.name}
      subTitle={subTitle}
      rightComponent={false}
      search={{
        show: true,
        placeholder: trans.administrationSearch,
        value: search,
        action: handleOnSearch,
      }}
    >
      <FlatList
        data={forms}
        renderItem={renderItem}
        keyExtractor={(item, index) => index.toString()}
        onEndReachedThreshold={0.5}
        ListFooterComponent={isLoading ? <ActivityIndicator size="large" color="#0000ff" /> : null}
      />
      {loadMore && (
        <Button
          onPress={() => {
            setIsLoading(true);
            setPage(page + 1);
          }}
        >
          {trans.loadMore}
        </Button>
      )}
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  listItemContainer: {
    position: 'relative',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 15,
  },
  syncButton: {
    backgroundColor: 'transparent',
  },
});

export default UpdateForm;
