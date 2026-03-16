import { Text, View } from '@tarojs/components';
import { userAppComponentTokens, userAppSemanticTokens } from '../theme/tokens';

type StatusTone = 'info' | 'success' | 'warning';

const TONE_COLOR: Record<StatusTone, string> = {
  info: userAppSemanticTokens.action.primary,
  success: userAppSemanticTokens.state.success,
  warning: userAppSemanticTokens.state.warning,
};

type StatusCardProps = {
  label: string;
  value: string;
  tone?: StatusTone;
};

export function StatusCard({ label, value, tone = 'info' }: StatusCardProps) {
  const tokens = userAppComponentTokens.statusCard;

  return (
    <View
      style={{
        background: tokens.background,
        border: `1px solid ${tokens.borderColor}`,
        borderRadius: tokens.radius,
        marginBottom: tokens.marginBottom,
        padding: tokens.padding,
      }}
    >
      <Text style={{ color: tokens.labelColor, display: 'block', fontSize: tokens.labelFontSize }}>{label}</Text>
      <Text style={{ color: TONE_COLOR[tone], display: 'block', fontSize: tokens.valueFontSize, fontWeight: '600', marginTop: tokens.valueMarginTop }}>
        {value}
      </Text>
    </View>
  );
}
