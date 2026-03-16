import { View } from '@tarojs/components';
import { userAppComponentTokens } from '../theme/tokens';
import { UiButton } from './UiButton';
import { UiCard } from './UiCard';
import { UiText } from './UiText';

type EmptyStateCardProps = {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
};

export function EmptyStateCard({ title, description, actionLabel, onAction }: EmptyStateCardProps) {
  const tokens = userAppComponentTokens.emptyState;

  return (
    <UiCard
      style={{
        background: tokens.background,
        borderStyle: 'dashed',
        borderColor: tokens.borderColor,
        borderRadius: tokens.radius,
        display: 'flex',
        flexDirection: 'column',
        gap: tokens.gap,
        padding: tokens.padding,
      }}
    >
      <UiText variant="title" style={{ fontSize: tokens.titleFontSize }}>
        {title}
      </UiText>
      <UiText variant="body" tone="secondary">
        {description}
      </UiText>
      {actionLabel && onAction ? (
        <View style={{ marginTop: tokens.actionMarginTop }}>
          <UiButton variant="secondary" onClick={onAction}>
            {actionLabel}
          </UiButton>
        </View>
      ) : null}
    </UiCard>
  );
}
