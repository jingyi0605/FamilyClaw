import { View } from '@tarojs/components';
import { type CSSProperties, type PropsWithChildren } from 'react';
import { userAppComponentTokens } from '../theme/tokens';

type UiCardVariant = 'default' | 'muted' | 'warning';

type UiCardProps = PropsWithChildren<{
  variant?: UiCardVariant;
  style?: CSSProperties;
}>;

export function UiCard({ children, variant = 'default', style }: UiCardProps) {
  const tokens = userAppComponentTokens.card[variant];

  return (
    <View
      style={{
        background: tokens.background,
        border: `1px solid ${tokens.borderColor}`,
        borderRadius: tokens.radius,
        padding: tokens.padding,
        ...style,
      }}
    >
      {children}
    </View>
  );
}
