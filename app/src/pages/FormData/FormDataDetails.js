import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, Alert } from 'react-native';
import { ListItem, Image, Button } from '@rneui/themed';
import moment from 'moment';
import * as Linking from 'expo-linking';
import { FormState, UIState } from '../../store';
import { cascades, helpers, i18n } from '../../lib';
import { BaseLayout } from '../../components';
import FormDataNavigation from './FormDataNavigation';
import { QUESTION_TYPES } from '../../lib/constants';

const ImageView = ({ label, uri, textTestID, imageTestID }) => (
  <View style={styles.containerImage}>
    <Text style={styles.title} testID={textTestID}>
      {label}
    </Text>
    <Image source={{ uri }} testID={imageTestID} style={styles.image} />
  </View>
);

const SubtitleContent = ({ index, answer, type, source = null, option = [] }) => {
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const [cascadeValue, setCascadeValue] = useState(null);

  const openFileManager = async (uri) => {
    const supported = await Linking.canOpenURL(uri);
    if (supported) {
      await Linking.openURL(uri);
    } else {
      Alert.alert("Don't know how to open this URL:", uri);
    }
  };

  const fetchCascade = useCallback(async () => {
    if (source) {
      const cascadeID = parseInt(answer, 10);
      const [csValue, db] = await cascades.loadDataSource(source, cascadeID);
      setCascadeValue(csValue);
      await db.closeAsync();
    }
  }, [answer, source]);

  useEffect(() => {
    fetchCascade();
  }, [fetchCascade]);

  switch (type) {
    case QUESTION_TYPES.geo:
      return (
        <View testID={`text-type-geo-${index}`}>
          <Text>
            {trans.latitude}: {answer?.[0]}
          </Text>
          <Text>
            {trans.longitude}: {answer?.[1]}
          </Text>
        </View>
      );
    case QUESTION_TYPES.cascade:
      return <Text testID={`text-answer-${index}`}>{cascadeValue ? cascadeValue.name : '-'}</Text>;
    case QUESTION_TYPES.date:
      return (
        <Text testID={`text-answer-${index}`}>
          {answer ? moment(answer).format('YYYY-MM-DD') : '-'}
        </Text>
      );
    case QUESTION_TYPES.option:
    case QUESTION_TYPES.multiple_option:
      return (
        <Text testID={`text-answer-${index}`}>
          {answer
            ?.map((a) => {
              const findOption = option?.find((o) => o?.value === a);
              return findOption?.label;
            })
            ?.join(', ')}
        </Text>
      );
    case QUESTION_TYPES.attachment:
      if (!answer) {
        return <Text testID={`text-type-attachment-${index}`}>-</Text>;
      }
      return (
        <View testID={`text-type-attachment-${index}`} style={{ width: '100%' }}>
          <Text
            testID={`text-answer-${index}`}
            style={{ color: 'blue', textDecorationLine: 'underline' }}
          >
            {answer.split('/').pop()}
          </Text>
          <Button
            title={trans.openFileButton}
            onPress={() => openFileManager(answer)}
            testID={`open-file-button-${index}`}
            buttonStyle={{ width: '100%', backgroundColor: '#1E90FF', marginTop: 8 }}
          />
        </View>
      );
    default:
      return <Text testID={`text-answer-${index}`}>{answer || answer === 0 ? answer : '-'}</Text>;
  }
};

const FormDataDetails = ({ navigation, route }) => {
  const selectedForm = FormState.useState((s) => s.form);
  const currentValues = FormState.useState((s) => s.currentValues);
  const [currentPage, setCurrentPage] = useState(0);

  const { json: formJSON } = selectedForm || {};

  const form = formJSON ? JSON.parse(formJSON) : {};
  const currentGroup = form?.question_group?.[currentPage] || [];
  const totalPage = form?.question_group?.length || 0;
  const questions = currentGroup?.question || [];
  const numberOfRepeat =
    Object.entries(currentValues).filter(([key]) => {
      const [questionID] = key.split('-');
      return questionID === `${questions?.[0]?.id}`;
    }).length || 1;
  // Create a sections array for the repeatable questions
  const sections = Array.from({ length: numberOfRepeat }, (_, i) => ({
    repeatIndex: i,
    title: currentGroup?.repeatable
      ? `${currentGroup?.label || currentGroup?.name} #${i + 1}`
      : currentGroup?.label || currentGroup?.name,
    data: questions.map((q, qx) => ({
      ...q,
      id: i === 0 ? q.id : `${q.id}-${i}`,
      keyform: `${i + 1}.${qx + 1}`,
    })),
  }));

  useEffect(
    () =>
      navigation.addListener('beforeRemove', (e) => {
        // Prevent default behavior of leaving the screen
        e.preventDefault();

        if (Object.keys(currentValues).length) {
          FormState.update((s) => {
            s.currentValues = {};
          });
          navigation.dispatch(e.data.action);
        }
      }),
    [navigation, currentValues],
  );

  return (
    <BaseLayout title={route?.params?.name} rightComponent={false}>
      <ScrollView>
        {sections.map((section) => (
          <View key={section.repeatIndex}>
            <Text style={styles.sectionTitle}>{section.title}</Text>
            {section.data.map((q, qIndex) => {
              const { id, label, type, source, option } = q;
              const answer = currentValues[id] || currentValues[`${id}-${section.repeatIndex}`];

              if (q.type === QUESTION_TYPES.attachment && currentValues?.[q.id]) {
                const fileName = answer.split('/').pop();
                const fileExtension = fileName.split('.').pop();
                if (helpers.isImageFile(fileExtension)) {
                  return (
                    <ImageView
                      key={q.id}
                      label={q.label}
                      uri={answer}
                      textTestID={`text-question-${qIndex}`}
                      imageTestID={`image-question-${qIndex}`}
                    />
                  );
                }
              }
              if (
                [QUESTION_TYPES.photo, QUESTION_TYPES.signature].includes(q.type) &&
                currentValues?.[q.id]
              ) {
                return (
                  <ImageView
                    key={q.id}
                    label={q.label}
                    uri={answer}
                    textTestID={`text-question-${qIndex}`}
                    imageTestID={`image-question-${qIndex}`}
                  />
                );
              }
              return (
                <ListItem key={q.keyform} bottomDivider>
                  <ListItem.Content>
                    <ListItem.Title testID={`text-question-${qIndex}`}>{label}</ListItem.Title>
                    <SubtitleContent
                      index={qIndex}
                      answer={answer}
                      type={type}
                      source={source}
                      option={option}
                    />
                  </ListItem.Content>
                </ListItem>
              );
            })}
          </View>
        ))}
      </ScrollView>
      <FormDataNavigation
        totalPage={totalPage}
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
      />
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  title: {
    fontWeight: '700',
    fontSize: 14,
    marginBottom: 4,
  },
  sectionTitle: {
    fontWeight: '700',
    fontSize: 14,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  containerImage: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    padding: 16,
    backgroundColor: 'white',
    borderWidth: 1,
    borderTopColor: 'transparent',
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderBottomColor: 'silver',
  },
  image: {
    width: '100%',
    height: 200,
    aspectRatio: 1,
  },
});

export default FormDataDetails;
