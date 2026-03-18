/**
 * RnFormItem - 表单字段容器
 */
import type { ReactNode } from 'react';
import { View, StyleSheet } from 'react-native';
import { rnFoundationTokens, rnSemanticTokens } from '../tokens';
import { RnText } from './RnText';

interface RnFormItemProps {
  label: string;
  required?: boolean;
  hint?: string;
  children: ReactNode;
}

export function RnFormItem({ label, required, hint, children }: RnFormItemProps) {
  return (
    <View style={styles.container}>
      <View style={styles.labelRow}>
        <RnText variant="label">{label}</RnText>
        {required ? (
          <RnText variant="caption" tone="danger" style={styles.required}>*</RnText>
        ) : null}
      </View>
      {children}
      {hint ? (
        <RnText variant="caption" tone="tertiary" style={styles.hint}>{hint}</RnText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: rnFoundationTokens.spacing.sm,
  },
  labelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: rnFoundationTokens.spacing.xs,
  },
  required: {
    marginLeft: 2,
  },
  hint: {
    marginTop: rnFoundationTokens.spacing.xs,
  },
});
