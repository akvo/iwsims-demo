import React from 'react';
import { View, TouchableOpacity } from 'react-native';
import { Text, Icon, Divider } from '@rneui/themed';
import { FormState } from '../../store';
import styles from '../styles';

const RepeatSection = ({ group, repeatIndex }) => {
  // Skip rendering section title for the first instance (index 0)
  if (repeatIndex === 0) {
    return null;
  }

  const handleRemoveRepeat = () => {
    FormState.update((s) => {
      // Get current repeats for this group
      const currentRepeats = s.repeats || {};
      const groupRepeats = currentRepeats[group.id] || [0];

      // Filter out this repeat index
      const updatedRepeats = groupRepeats.filter((idx) => idx !== repeatIndex);
      s.repeats = {
        ...currentRepeats,
        [group.id]: updatedRepeats,
      };
    });
  };

  return (
    <View style={styles.repeatSectionContainer}>
      <Divider style={styles.repeatDivider} />
      <View style={styles.repeatSectionHeader}>
        <Text style={styles.repeatSectionTitle}>
          {`${group.label || group.name} #${repeatIndex + 1}`}
        </Text>
        <TouchableOpacity
          style={styles.repeatSectionRemove}
          onPress={handleRemoveRepeat}
          testID={`remove-repeat-${group.id}-${repeatIndex}`}
        >
          <Icon type="ionicon" name="trash-outline" size={20} color="#cc0000" />
        </TouchableOpacity>
      </View>
    </View>
  );
};

export default RepeatSection;
