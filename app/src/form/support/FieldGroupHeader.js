import React from 'react';
import { View } from 'react-native';
import { Text } from '@rneui/themed';
import styles from '../styles';

const FieldGroupHeader = ({ description, index, label }) => (
  <View>
    <View style={styles.fieldGroupHeader}>
      <Text style={styles.fieldGroupName} testID="text-name">
        {`${index + 1}. ${label}`}
      </Text>
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

export default FieldGroupHeader;
