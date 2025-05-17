import React from 'react';
import { TouchableOpacity, View } from 'react-native';
import { Text, Icon } from '@rneui/themed';
import styles from '../styles';
import { FormState } from '../../store';

const FieldGroupHeader = ({ description, index, label, repeatable, id }) => {
  const handleDuplicateGroup = () => {
    if (repeatable) {
      FormState.update((s) => {
        // If there's already a repeats array for this group, add to it
        const currentRepeats = s.repeats || {};
        const groupRepeats = currentRepeats[id] || [0];

        // Add next repeat index (which is the current max + 1)
        const nextRepeatIndex = Math.max(...groupRepeats) + 1;
        // Update the state with the new repeat
        s.repeats = {
          ...s.repeats,
          [id]: [...groupRepeats, nextRepeatIndex],
        };
      });
    }
  };

  return (
    <View>
      <View style={styles.fieldGroupHeader}>
        <Text style={styles.fieldGroupName} testID="text-name">
          {`${index + 1}. ${label}`}
        </Text>
        {repeatable && (
          <TouchableOpacity
            style={styles.fieldGroupCopy}
            testID="copy-button"
            onPress={handleDuplicateGroup}
          >
            <Icon type="ionicon" name="copy-outline" size={20} color="#000" testID="copy" />
          </TouchableOpacity>
        )}
      </View>
      <View style={styles.fieldGroupDescContainer}>
        {description && (
          <Text style={styles.fieldGroupDescription} testID="text-description">
            {description}
          </Text>
        )}
      </View>
    </View>
  );
};

export default FieldGroupHeader;
