import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { View, Text } from 'react-native';
import { Dropdown } from 'react-native-element-dropdown';

import { FieldLabel } from '../support';
import styles from '../styles';
import { FormState } from '../../store';
import { i18n, cascades } from '../../lib';

const TypeCascade = ({
  onChange,
  value,
  keyform,
  id,
  label,
  required,
  source,
  requiredSign = '*',
  disabled = false,
  tooltip = null,
}) => {
  const [dataSource, setDataSource] = useState([]);
  const [dropdownItems, setDropdownItems] = useState([]);
  const prevAdmAnswer = FormState.useState((s) => s.prevAdmAnswer);
  const activeLang = FormState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const requiredValue = required ? requiredSign : null;
  const {
    cascade_parent: cascadeParent,
    cascade_type: cascadeType,
    parent_id: parentId,
  } = source || {};

  const groupBy = (array, property) => {
    const gd = array
      .sort((a, b) => a?.name?.localeCompare(b?.name))
      .reduce((groups, item) => {
        const key = item[property];
        if (!groups[key]) {
          groups[key] = [];
        }
        groups[key].push(item);
        return groups;
      }, {});
    const groupedData = {};
    Object.entries(gd).forEach(([key, val]) => {
      groupedData[key] = val;
    });
    return groupedData;
  };

  const handleOnChange = (index, val) => {
    const nextIndex = index + 1;
    const updatedItems = dropdownItems
      .slice(0, nextIndex)
      .map((d, dx) => (dx === index ? { ...d, value: val } : d));

    const options = dataSource?.filter((d) => d?.parent === val);

    if (options.length) {
      updatedItems.push({
        options,
        value: null,
      });
    }
    const dropdownValues = updatedItems.filter((dd) => dd.value);
    const finalValues = dropdownValues.slice(-1).map((dd) => dd.value);
    onChange(id, finalValues);
    if (finalValues) {
      const { options: selectedOptions, value: selectedValue } = dropdownValues.pop();
      const findSelected = selectedOptions?.find((o) => o.id === selectedValue);
      const cascadeName = findSelected?.name;
      FormState.update((s) => {
        s.cascades = { ...s.cascades, [id]: cascadeName };
        s.prevAdmAnswer = source?.file === 'administrator.sqlite' ? finalValues : s.prevAdmAnswer;
      });
    }
    setDropdownItems(updatedItems);
  };

  const initialDropdowns = useMemo(() => {
    const parentIDs =
      cascadeParent === 'administrator.sqlite' ? prevAdmAnswer || [] : parentId || [0];
    const filterDs = dataSource
      ?.filter((ds) => {
        if (cascadeType && ds?.entity) {
          return ds.entity === cascadeType;
        }
        return ds;
      })
      ?.filter((ds) => {
        if (cascadeParent) {
          return parentIDs.includes(ds?.parent);
        }
        return (
          parentIDs.includes(ds?.parent) ||
          parentIDs.includes(ds?.id) ||
          value?.includes(ds?.id) ||
          value?.includes(ds?.parent)
        );
      });

    if (cascadeParent === 'administrator.sqlite') {
      if (filterDs?.length) {
        const defaultValue = filterDs.find(
          (d) => d?.name === value?.[0] || d?.id === value?.[0],
        )?.id;
        return [
          {
            options: filterDs,
            value: defaultValue || value?.[0] || null,
          },
        ];
      }
      return [];
    }
    const groupedDs = groupBy(filterDs, 'parent');
    if (parentIDs.length > 1 && Object.keys(groupedDs).length > 1) {
      const parentOptions = Object.keys(groupedDs)
        .map((keyID) => dataSource.find((d) => d?.id === parseInt(keyID, 10)))
        .filter((d) => d);
      return value
        ? value.map((val, vx) => {
            const options = dataSource?.filter((d) =>
              vx === 0 ? parentIDs.includes(d?.id) : d?.parent === parseInt(value?.[vx - 1], 10),
            );
            return {
              options,
              value: parseInt(val, 10),
            };
          })
        : [
            {
              options: parentOptions,
              value: value?.[0] || null,
            },
          ];
    }
    return Object.values(groupedDs).map((options, ox) => {
      const defaultValue = value?.[ox] || null;
      const answer =
        typeof defaultValue === 'string'
          ? options.find((o) => o?.name === defaultValue)?.id
          : defaultValue;
      return {
        options,
        value: answer,
      };
    });
  }, [dataSource, cascadeParent, cascadeType, parentId, prevAdmAnswer, value]);

  const loadCascadeData = useCallback(async () => {
    const [rows, _db] = await cascades.loadDataSource(source);
    setDataSource(rows);
    // Close database connection
    await _db.closeAsync();

    // Update entity options if cascadeType is defined
    if (cascadeType) {
      FormState.update((s) => {
        s.entityOptions[id] = rows?.filter((a) => a?.entity === cascadeType);
      });
    }

    // Find and update cascade name if value exists
    if (source && value?.length) {
      const cascadeID = value.slice(-1)[0];
      // Filter rows with cascadeID instead of making another loadDataSource call
      const csValue = rows?.find((row) => row.id === cascadeID);
      if (csValue) {
        FormState.update((s) => {
          s.cascades = {
            ...s.cascades,
            [id]: csValue.name,
          };
        });
      }
    }
  }, [source, value, id, cascadeType]);

  useEffect(() => {
    loadCascadeData();
  }, [loadCascadeData]);

  useEffect(() => {
    if (
      (dropdownItems.length === 0 && initialDropdowns.length) ||
      (source?.cascade_parent && prevAdmAnswer)
    ) {
      /**
       * Reset entity cascade options when the prevAdmAnswer changes.
       */
      setDropdownItems(initialDropdowns);
    }
  }, [dropdownItems, initialDropdowns, dataSource, prevAdmAnswer, id, source]);

  const handleDefaultValue = useCallback(() => {
    if (typeof value?.[0] === 'string' && dropdownItems.length) {
      const lastItem = dropdownItems.slice(-1)?.[0] || { value: null, options: [] };
      if (lastItem?.value) {
        onChange(id, [lastItem.value]);
      }
    }
  }, [value, id, dropdownItems, onChange]);

  useEffect(() => {
    handleDefaultValue();
  }, [handleDefaultValue]);

  if (!dropdownItems.length) {
    return null;
  }

  return (
    <View testID="view-type-cascade">
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
      <Text testID="text-values" style={styles.cascadeValues}>
        {value}
      </Text>
      <View style={styles.cascadeContainer}>
        {dropdownItems.map((item, index) => {
          const hasSearch = item?.options.length > 3;
          const style = disabled
            ? { ...styles.dropdownField, ...styles.dropdownFieldDisabled }
            : styles.dropdownField;
          return (
            <Dropdown
              // eslint-disable-next-line react/no-array-index-key
              key={index}
              labelField="name"
              valueField="id"
              testID={`dropdown-cascade-${index}`}
              data={item?.options}
              search={hasSearch}
              searchPlaceholder={trans.searchPlaceholder}
              onChange={({ id: selectedID }) => handleOnChange(index, selectedID)}
              value={item.value}
              style={style}
              placeholder={trans.selectItem}
              disable={disabled}
            />
          );
        })}
      </View>
    </View>
  );
};

export default TypeCascade;
