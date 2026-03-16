import { View } from '@tarojs/components';
import { type CSSProperties, type PropsWithChildren } from 'react';
import { userAppComponentTokens } from '../theme/tokens';

type UiCardVariant = 'default' | 'muted' | 'warning';

type UiCardProps = PropsWithChildren<{
  variant?: UiCardVariant;
  className?: string;
  onClick?: () => void;
  style?: CSSProperties;
}>;

export function UiCard({ children, variant = 'default', className, onClick, style }: UiCardProps) {
  const tokens = userAppComponentTokens.card[variant];

  return (
    <View
      className={className}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
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
