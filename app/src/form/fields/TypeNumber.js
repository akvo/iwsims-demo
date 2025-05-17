/* eslint-disable react/jsx-props-no-spreading */
import React, { useEffect, useState } from 'react';
import { View } from 'react-native';
import { Input } from '@rneui/themed';
import { FieldLabel } from '../support';
import styles from '../styles';
import { addPreffix, addSuffix } from './TypeInput';
import { strToFunction } from '../lib';

const TypeNumber = ({
  onChange,
  value,
  keyform,
  id,
  label,
  required,
  requiredSign = '*',
  disabled = false,
  addonAfter = null,
  addonBefore = null,
  tooltip = null,
  questions = [],
  fn = null,
}) => {
  const [fieldColor, setFieldColor] = useState(null);
  const requiredValue = required ? requiredSign : null;
  const { fnColor } = fn || {};

  useEffect(() => {
    if (typeof fnColor === 'string') {
      try {
        const allQuestions = questions.flatMap((q) => q.question);
        const fnColorFunction = strToFunction(fnColor, { [id]: value }, allQuestions);
        if (typeof fnColorFunction === 'function') {
          const fnColorValue = fnColorFunction();
          if (fnColorValue && fnColorValue !== fieldColor) {
            setFieldColor(fnColorValue);
          }
        }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Error in fnColor function:', error);
      }
    }
  }, [fnColor, fieldColor, id, value, questions]);

  return (
    <View>
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
      <Input
        inputContainerStyle={{
          ...styles.inputFieldContainer,
          backgroundColor: fieldColor || 'white',
        }}
        keyboardType="numeric"
        onChangeText={(val) => {
          if (onChange) {
            onChange(id, val);
          }
        }}
        value={value}
        testID="type-number"
        {...addPreffix(addonBefore)}
        {...addSuffix(addonAfter)}
        disabled={disabled}
      />
    </View>
  );
};

export default TypeNumber;
