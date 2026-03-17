import { View } from '@tarojs/components';
import { type ReactNode } from 'react';
import { userAppComponentTokens } from '../theme/tokens';
import { UiButton } from './UiButton';
import { UiCard } from './UiCard';
import { UiText } from './UiText';

type EmptyStateCardProps = {
  className?: string;
  icon?: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
  actionLabel?: string;
  onAction?: () => void;
};

export function EmptyStateCard({
  className,
  icon,
  title,
  description,
  action,
  actionLabel,
  onAction,
}: EmptyStateCardProps) {
  const tokens = userAppComponentTokens.emptyState;

  return (
    <UiCard
      className={className}
      style={{
        background: tokens.background,
        borderStyle: 'dashed',
        borderColor: tokens.borderColor,
        borderRadius: tokens.radius,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        gap: tokens.gap,
        padding: tokens.padding,
        alignSelf: 'stretch',
      }}
    >
      {icon ? <View>{icon}</View> : null}
      <UiText variant="title" style={{ fontSize: tokens.titleFontSize }}>
        {title}
      </UiText>
      <UiText variant="body" tone="secondary">
        {description}
      </UiText>
      {action ? <View style={{ marginTop: tokens.actionMarginTop }}>{action}</View> : null}
      {!action && actionLabel && onAction ? (
        <View style={{ marginTop: tokens.actionMarginTop }}>
          <UiButton variant="secondary" onClick={onAction}>
            {actionLabel}
          </UiButton>
        </View>
      ) : null}
    </UiCard>
  );
}
