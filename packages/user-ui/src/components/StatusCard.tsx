import { userAppComponentTokens, userAppSemanticTokens } from '../theme/tokens';
import { UiCard } from './UiCard';
import { UiText } from './UiText';

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
    <UiCard
      variant="muted"
      style={{
        marginBottom: tokens.marginBottom,
      }}
    >
      <UiText variant="caption" style={{ color: tokens.labelColor, fontSize: tokens.labelFontSize }}>
        {label}
      </UiText>
      <UiText variant="label" style={{ color: TONE_COLOR[tone], fontSize: tokens.valueFontSize, marginTop: tokens.valueMarginTop }}>
        {value}
      </UiText>
    </UiCard>
  );
}
