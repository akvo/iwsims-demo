import React, { useState } from 'react';
import { View } from 'react-native';
import { Text, Icon } from '@rneui/themed';
import styles from '../styles';
import AnimatedTooltip from '../../components/AnimatedTooltip';

const FieldLabel = ({ keyform, name, tooltip, requiredSign = null }) => {
  const [open, setOpen] = useState(false);
  const labelText = `${keyform}. ${name}`;
  const tooltipText = tooltip?.text;
  return (
    <View style={styles.fieldLabelContainer}>
      {requiredSign && (
        <Text style={styles.fieldRequiredIcon} testID="field-required-icon">
          {requiredSign}
        </Text>
      )}
      <View style={styles.fieldLabel}>
        <View style={{ flexDirection: 'row' }}>
          <Text testID="field-label">
            {labelText}
            {tooltipText && (
              <Text>
                {' '}
                <Icon
                  name="information-circle"
                  type="ionicon"
                  size={18}
                  testID="field-tooltip-icon"
                  onPress={() => setOpen(!open)}
                />
              </Text>
            )}
          </Text>
        </View>
        <AnimatedTooltip visible={open} content={tooltipText} style={{ width: '100%' }} />
      </View>
    </View>
  );
};

export default FieldLabel;
