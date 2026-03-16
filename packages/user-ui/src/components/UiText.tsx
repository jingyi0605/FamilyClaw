import { Text } from '@tarojs/components';
import { type CSSProperties, type PropsWithChildren } from 'react';
import { userAppComponentTokens, userAppSemanticTokens } from '../theme/tokens';

type UiTextVariant = 'body' | 'caption' | 'label' | 'title' | 'sectionTitle';
type UiTextTone = 'primary' | 'secondary' | 'tertiary' | 'inverse' | 'success' | 'warning' | 'danger' | 'info';

const TONE_COLOR: Record<UiTextTone, string> = {
  primary: userAppSemanticTokens.text.primary,
  secondary: userAppSemanticTokens.text.secondary,
  tertiary: userAppSemanticTokens.text.tertiary,
  inverse: userAppSemanticTokens.text.inverse,
  success: userAppSemanticTokens.state.success,
  warning: userAppSemanticTokens.state.warning,
  danger: userAppSemanticTokens.state.danger,
  info: userAppSemanticTokens.action.primary,
};

type UiTextProps = PropsWithChildren<{
  variant?: UiTextVariant;
  tone?: UiTextTone;
  block?: boolean;
  style?: CSSProperties;
}>;

export function UiText({
  children,
  variant = 'body',
  tone,
  block = true,
  style,
}: UiTextProps) {
  const tokens = userAppComponentTokens.text[variant];

  return (
    <Text
      style={{
        color: tone ? TONE_COLOR[tone] : tokens.color,
        display: block ? 'block' : undefined,
        fontSize: tokens.fontSize,
        fontWeight: tokens.fontWeight,
        lineHeight: tokens.lineHeight,
        ...style,
      }}
    >
      {children}
    </Text>
  );
}
