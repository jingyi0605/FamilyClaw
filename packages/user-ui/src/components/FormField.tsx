import { View } from '@tarojs/components';
import { type PropsWithChildren } from 'react';
import { userAppComponentTokens } from '../theme/tokens';
import { UiText } from './UiText';

type FormFieldProps = PropsWithChildren<{
  label: string;
  hint?: string;
}>;

export function FormField({ label, hint, children }: FormFieldProps) {
  const tokens = userAppComponentTokens.field;

  return (
    <View style={{ display: 'flex', flexDirection: 'column', gap: tokens.gap }}>
      <UiText variant="label">{label}</UiText>
      {children}
      {hint ? <UiText variant="caption" tone="secondary" style={{ marginTop: tokens.hintMarginTop }}>{hint}</UiText> : null}
    </View>
  );
}
