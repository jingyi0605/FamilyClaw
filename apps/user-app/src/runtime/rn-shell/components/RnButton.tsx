/**
 * RnButton - 按钮组件
 */
import type { ReactNode } from 'react';
import { Pressable, ActivityIndicator, StyleSheet, type ViewStyle } from 'react-native';
import { rnSemanticTokens, rnFoundationTokens, rnComponentTokens } from '../tokens';
import { RnText } from './RnText';

interface RnButtonProps {
  children: ReactNode;
  onPress?: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: 'primary' | 'secondary';
  style?: ViewStyle;
}

export function RnButton({
  children,
  onPress,
  loading = false,
  disabled = false,
  variant = 'primary',
  style,
}: RnButtonProps) {
  const isDisabled = disabled || loading;
  const isPrimary = variant === 'primary';

  return (
    <Pressable
      onPress={isDisabled ? undefined : onPress}
      style={({ pressed }) => [
        styles.base,
        isPrimary ? styles.primary : styles.secondary,
        pressed && !isDisabled && styles.pressed,
        isDisabled && styles.disabled,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator
          size="small"
          color={isPrimary ? rnSemanticTokens.text.inverse : rnSemanticTokens.action.primary}
        />
      ) : (
        <RnText
          variant="label"
          tone={isPrimary ? 'inverse' : 'primary'}
          style={styles.label}
        >
          {children}
        </RnText>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: rnComponentTokens.button.minHeight,
    borderRadius: rnComponentTokens.button.borderRadius,
    paddingHorizontal: rnComponentTokens.button.paddingHorizontal,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
  },
  primary: {
    backgroundColor: rnSemanticTokens.action.primary,
  },
  secondary: {
    backgroundColor: rnSemanticTokens.surface.card,
    borderWidth: 1,
    borderColor: rnSemanticTokens.border.default,
  },
  pressed: {
    opacity: 0.85,
  },
  disabled: {
    opacity: 0.5,
  },
  label: {
    textAlign: 'center',
    fontSize: rnComponentTokens.button.fontSize,
    fontWeight: rnComponentTokens.button.fontWeight,
  },
});
