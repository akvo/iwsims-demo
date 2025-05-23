import React, { useMemo } from 'react';
import { View } from 'react-native';
import { Dropdown } from 'react-native-element-dropdown';
import { FieldLabel, OptionItem } from '../support';
import styles from '../styles';
import { FormState } from '../../store';
import { i18n } from '../../lib';

const TypeOption = ({
  onChange,
  value,
  keyform,
  id,
  label,
  required,
  option = [],
  tooltip = null,
  requiredSign = '*',
  disabled = false,
}) => {
  const showSearch = useMemo(() => option.length > 3, [option]);
  const activeLang = FormState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const requiredValue = required ? requiredSign : null;
  const color = useMemo(() => {
    const currentValue = value?.[0];
    return option.find((x) => x.value === currentValue)?.color;
  }, [value, option]);

  const selectedStyle = useMemo(() => {
    const currentValue = value?.[0];
    const backgroundColor = option.find((x) => x.value === currentValue)?.color;
    if (!color) {
      return {};
    }
    return {
      marginLeft: -8,
      marginRight: -27,
      borderRadius: 5,
      paddingTop: 8,
      paddingLeft: 8,
      paddingBottom: 8,
      color: '#FFF',
      backgroundColor,
    };
  }, [value, color, option]);
  const style = disabled
    ? { ...styles.dropdownField, ...styles.dropdownFieldDisabled }
    : styles.dropdownField;

  return (
    <View style={styles.optionContainer}>
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
      <Dropdown
        style={style}
        selectedTextStyle={selectedStyle}
        data={option}
        search={showSearch}
        maxHeight={300}
        labelField="label"
        valueField="value"
        searchPlaceholder={trans.searchPlaceholder}
        value={value?.[0] || ''}
        onChange={({ value: optValue }) => {
          if (onChange) {
            onChange(id, [optValue]);
          }
        }}
        renderItem={OptionItem}
        testID="type-option-dropdown"
        placeholder={trans.selectItem}
        disable={disabled}
      />
    </View>
  );
};

export default TypeOption;
