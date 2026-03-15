import { Text, View } from '@tarojs/components';
import { userAppTokens } from '../theme/tokens';

type StatusTone = 'info' | 'success' | 'warning';

const TONE_COLOR: Record<StatusTone, string> = {
  info: userAppTokens.colorPrimary,
  success: userAppTokens.colorSuccess,
  warning: userAppTokens.colorWarning,
};

type StatusCardProps = {
  label: string;
  value: string;
  tone?: StatusTone;
};

export function StatusCard({ label, value, tone = 'info' }: StatusCardProps) {
  return (
    <View
      style={{
        background: '#f9fbff',
        border: `1px solid ${userAppTokens.colorBorder}`,
        borderRadius: userAppTokens.radiusMd,
        marginBottom: userAppTokens.spacingXs,
        padding: userAppTokens.spacingSm,
      }}
    >
      <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '22px' }}>{label}</Text>
      <Text style={{ color: TONE_COLOR[tone], display: 'block', fontSize: '28px', fontWeight: '600', marginTop: '4px' }}>
        {value}
      </Text>
    </View>
  );
}
