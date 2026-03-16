import { Text, View } from '@tarojs/components';
import { type CSSProperties } from 'react';
import { userAppComponentTokens } from '../theme/tokens';

type UiTagVariant = 'neutral' | 'info' | 'success' | 'warning';

type UiTagProps = {
  label: string;
  variant?: UiTagVariant;
  style?: CSSProperties;
};

export function UiTag({ label, variant = 'neutral', style }: UiTagProps) {
  const tokens = userAppComponentTokens.tag;
  const variantTokens = tokens.variant[variant];

  return (
    <View
      style={{
        background: variantTokens.background,
        border: `1px solid ${variantTokens.borderColor}`,
        borderRadius: tokens.radius,
        padding: `${tokens.paddingBlock} ${tokens.paddingInline}`,
        ...style,
      }}
    >
      <Text style={{ color: variantTokens.textColor, fontSize: tokens.fontSize }}>{label}</Text>
    </View>
  );
}
