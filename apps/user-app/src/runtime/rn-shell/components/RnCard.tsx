/**
 * RnCard - 卡片容器
 *
 * variant: default | muted | warning
 */
import { View, type ViewProps } from 'react-native';
import { rnComponentTokens } from '../tokens';

type CardVariant = 'default' | 'muted' | 'warning';

interface RnCardProps extends ViewProps {
  variant?: CardVariant;
}

export function RnCard({ variant = 'default', style, children, ...rest }: RnCardProps) {
  const cardStyle = rnComponentTokens.card[variant];

  return (
    <View
      style={[
        cardStyle,
        rnComponentTokens.shadow.sm,
        { marginBottom: 8 },
        style,
      ]}
      {...rest}
    >
      {children}
    </View>
  );
}
