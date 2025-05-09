import React, { useMemo, useCallback } from 'react';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { View, FlatList, StyleSheet, Text, TouchableOpacity } from 'react-native';
import { BaseLayout } from '../components';
import { UIState, FormState } from '../store';
import { i18n } from '../lib';
import { getCurrentTimestamp } from '../form/lib';
import { SUBMISSION_TYPES } from '../lib/constants';

const ManageForm = ({ navigation, route }) => {
  const activeForm = FormState.useState((s) => s.form);
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const subTypesAvailable = useMemo(() => {
    try {
      const form = JSON.parse(activeForm.json.replace(/''/g, "'"));
      return form?.submission_types;
    } catch {
      return [];
    }
  }, [activeForm]);

  const goToNewForm = useCallback(() => {
    FormState.update((s) => {
      s.surveyStart = getCurrentTimestamp();
      s.prevAdmAnswer = null;
    });
    navigation.navigate('FormPage', {
      ...route?.params,
      newSubmission: true,
      submission_type: SUBMISSION_TYPES.registration,
    });
  }, [navigation, route]);

  const goToUpdateForm = useCallback(
    (submissionType) => {
      FormState.update((s) => {
        s.surveyStart = getCurrentTimestamp();
      });
      navigation.navigate('UpdateForm', {
        ...route?.params,
        newSubmission: true,
        submission_type: submissionType,
      });
    },
    [navigation, route],
  );

  const menuItems = useMemo(() => {
    const items = [];

    if (subTypesAvailable.includes(SUBMISSION_TYPES.registration)) {
      items.push({
        id: '1',
        title: trans.manageNewBlank,
        icon: 'clipboard-outline',
        onPress: goToNewForm,
        testID: 'goto-item-1',
      });
    }

    if (subTypesAvailable.includes(SUBMISSION_TYPES.monitoring)) {
      items.push({
        id: '2',
        title: trans.manageUpdate,
        icon: 'clipboard-edit-outline',
        onPress: () => goToUpdateForm(SUBMISSION_TYPES.monitoring),
        testID: 'goto-item-2',
      });
    }

    items.push({
      id: '3',
      title: `${trans.manageEditSavedForm} (${activeForm?.draft})`,
      icon: 'folder-open',
      onPress: () => navigation.navigate('FormData', { ...route?.params, showSubmitted: false }),
      testID: 'goto-item-3',
    });

    items.push({
      id: '4',
      title: `${trans.manageViewSubmitted} (${activeForm?.submitted})`,
      icon: 'eye',
      onPress: () => navigation.navigate('FormData', { ...route?.params, showSubmitted: true }),
      testID: 'goto-item-4',
    });

    return items;
  }, [subTypesAvailable, activeForm, trans, route, navigation, goToNewForm, goToUpdateForm]);

  const renderItem = ({ item }) => (
    <TouchableOpacity
      key={item.id}
      onPress={item.onPress}
      testID={item.testID}
      style={styles.itemContainer}
      activeOpacity={0.6}
    >
      <Icon name={item.icon} color="grey" size={18} />
      <View style={styles.itemContent}>
        <Text style={styles.itemTitle}>{item.title}</Text>
      </View>
      <Icon name="chevron-right" size={18} color="#ccc" />
    </TouchableOpacity>
  );

  return (
    <BaseLayout title={route?.params?.name} rightComponent={false}>
      <BaseLayout.Content>
        <View style={styles.container}>
          <FlatList
            data={menuItems}
            renderItem={renderItem}
            keyExtractor={(item) => item.id}
            testID="manage-form-list"
            contentContainerStyle={styles.flatListContent}
          />
        </View>
      </BaseLayout.Content>
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  flatListContent: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  itemContainer: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 16,
    paddingHorizontal: 16,
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  itemContent: {
    flex: 1,
    marginLeft: 10,
  },
  itemTitle: {
    fontSize: 16,
    color: '#212121',
  },
});

export default ManageForm;
