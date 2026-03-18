/**
 * RnText - 统一的文本组件
 *
 * variant: body | caption | label | title | hero
 * tone:    primary | secondary | tertiary | inverse | danger | warning | success
 */
import { Text, type TextProps, type TextStyle } from 'react-native';
import { rnComponentTokens, rnSemanticTokens } from '../tokens';

export type RnTextVariant = 'body' | 'caption' | 'label' | 'title' | 'hero';
export type RnTextTone =
  | 'primary'
  | 'secondary'
  | 'tertiary'
  | 'inverse'
  | 'danger'
  | 'warning'
  | 'success';

const TONE_COLORS: Record<RnTextTone, string> = {
  primary: rnSemanticTokens.text.primary,
  secondary: rnSemanticTokens.text.secondary,
  tertiary: rnSemanticTokens.text.tertiary,
  inverse: rnSemanticTokens.text.inverse,
  danger: rnSemanticTokens.state.danger,
  warning: rnSemanticTokens.state.warning,
  success: rnSemanticTokens.state.success,
};

interface RnTextProps extends TextProps {
  variant?: RnTextVariant;
  tone?: RnTextTone;
}

export function RnText({
  variant = 'body',
  tone,
  style,
  ...rest
}: RnTextProps) {
  const variantStyle = rnComponentTokens.text[variant] as TextStyle;
  const toneColor = tone ? { color: TONE_COLORS[tone] } : undefined;

  return <Text style={[variantStyle, toneColor, style]} {...rest} />;
}
