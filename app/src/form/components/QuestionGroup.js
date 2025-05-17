/* eslint-disable react/jsx-props-no-spreading */
import React, { useMemo, useRef, useEffect } from 'react';
import { View, SectionList, FlatList } from 'react-native';

import QuestionField from './QuestionField';
import { FieldGroupHeader, RepeatSection } from '../support';
import { FormState } from '../../store';
import styles from '../styles';

const QuestionGroup = ({ index, group, activeQuestions, dependantQuestions = [] }) => {
  // Get the repeats state for this group from FormState
  const repeatState = FormState.useState((s) => s.repeats);
  const repeats = useMemo(
    () => repeatState?.[group.id] || repeatState?.[group?.name] || [0],
    [repeatState, group.id, group?.name],
  );
  const values = FormState.useState((s) => s.currentValues);
  const prevAdmAnswer = FormState.useState((s) => s.prevAdmAnswer);
  const listRef = useRef(null);

  // Prepare sections data for SectionList when group is repeatable
  const sections = useMemo(
    () =>
      repeats.map((repeatIndex) => ({
        repeatIndex,
        title: repeatIndex !== 0 ? `${group.label || group.name} #${repeatIndex + 1}` : null,
        data: group.question.map((q, qx) => ({
          ...q,
          id: repeatIndex === 0 ? q.id : `${q.id}-${repeatIndex}`,
          keyform: `${repeatIndex + 1}.${qx + 1}`,
        })),
      })),
    [repeats, group],
  );

  // For non-repeatable groups, use the same question filtering and preparation as in Question component
  const questions = useMemo(() => {
    if (group?.question?.length) {
      const questionList = group.question.filter(
        (q) => (q?.extra?.type === 'entity' && prevAdmAnswer) || !q?.extra?.type,
      );
      const questionWithNumber = questionList.reduce((curr, q, i) => {
        if (q?.default_value && i === 0) {
          return [{ ...q, keyform: 0 }];
        }
        if (q?.default_value && i > 0) {
          return [...curr, { ...q, keyform: curr[i - 1].keyform }];
        }
        if (i === 0) {
          return [{ ...q, keyform: 1 }];
        }
        return [...curr, { ...q, keyform: curr[i - 1].keyform + 1 }];
      }, []);
      return questionWithNumber;
    }
    return [];
  }, [group, prevAdmAnswer]);

  // Handle onChange for non-repeatable groups
  const handleOnChange = (id, value) => {
    // Handle dependencies with dependantQuestions
    FormState.update((s) => {
      s.currentValues = { ...s.currentValues, [id]: value };
    });
  };

  useEffect(() => {
    if (listRef.current) {
      if (group?.repeatable) {
        listRef.current.scrollToLocation({
          animated: true,
          sectionIndex: 0,
          itemIndex: 0,
        });
      } else {
        listRef.current.scrollToOffset({ animated: true, offset: 0 });
      }
    }
  }, [index, group?.repeatable]);

  // Render header for repeatable groups in SectionList
  const renderSectionHeader = ({ section }) => {
    if (section.repeatIndex !== 0) {
      return <RepeatSection group={group} repeatIndex={section.repeatIndex} />;
    }
    return null;
  };

  // If group is repeatable, use SectionList with sections
  if (group?.repeatable) {
    return (
      <View style={{ paddingBottom: 48 }}>
        <FieldGroupHeader index={index} {...group} />

        <SectionList
          ref={listRef}
          sections={sections}
          keyExtractor={(item, itemIndex) => `question-${item.id}-${itemIndex}`}
          renderItem={({ item, section }) => {
            const fieldValue = values?.[item.id];

            return (
              <View key={`question-${item.id}`} style={styles.questionContainer}>
                <QuestionField
                  keyform={item.id}
                  field={item}
                  onChange={handleOnChange}
                  value={fieldValue}
                  questions={section.data}
                />
              </View>
            );
          }}
          renderSectionHeader={renderSectionHeader}
          stickySectionHeadersEnabled={false}
          extraData={[group, values, activeQuestions, dependantQuestions]}
          removeClippedSubviews={false}
        />
      </View>
    );
  }

  // For non-repeatable groups, use FlatList
  return (
    <View style={{ paddingBottom: 48 }}>
      <FieldGroupHeader index={index} {...group} />

      <FlatList
        ref={listRef}
        scrollEnabled
        data={questions}
        keyExtractor={(item) => `question-${item.id}`}
        renderItem={({ item: field }) => {
          const fieldValue = values?.[field.id];

          return (
            <View key={`question-${field.id}`} style={styles.questionContainer}>
              <QuestionField
                keyform={field.id}
                field={field}
                onChange={handleOnChange}
                value={fieldValue}
                questions={questions}
              />
            </View>
          );
        }}
        extraData={[group, values, activeQuestions, dependantQuestions]}
        removeClippedSubviews={false}
      />
    </View>
  );
};

export default QuestionGroup;
