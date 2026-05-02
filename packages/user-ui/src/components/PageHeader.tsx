import { View } from '@tarojs/components';
import { type CSSProperties, type ReactNode } from 'react';
import { userAppComponentTokens } from '../theme/tokens';
import { UiText } from './UiText';

type PageHeaderProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
  actionsClassName?: string;
  style?: CSSProperties;
  align?: 'start' | 'end';
};

export function PageHeader({
  title,
  description,
  actions,
  className,
  actionsClassName,
  style,
  align = 'start',
}: PageHeaderProps) {
  const tokens = userAppComponentTokens.pageHeader;
  const hasTabActions = actionsClassName?.includes('page-header__actions--tabs') ?? false;
  const containerGap = hasTabActions ? `calc(${tokens.gap} * 2)` : tokens.gap;

  return (
    <View
      className={className}
      style={{
        display: 'flex',
        flexDirection: 'row',
        flexWrap: 'wrap',
        alignItems: align === 'end' ? 'flex-end' : 'flex-start',
        justifyContent: 'flex-start',
        gap: containerGap,
        marginBottom: tokens.marginBottom,
        ...style,
      }}
    >
      <View className="page-header__content" style={{ display: 'flex', flexDirection: 'column', gap: tokens.titleGap, minWidth: 0 }}>
        <UiText className="page-header__title" variant="title" style={{ fontSize: tokens.titleFontSize }}>
          {title}
        </UiText>
        {description ? (
          <UiText className="page-header__desc" tone="secondary" style={{ color: tokens.descriptionColor, fontSize: tokens.descriptionFontSize }}>
            {description}
          </UiText>
        ) : null}
      </View>
      {actions ? (
        <View
          className={`page-header__actions ${actionsClassName ?? ''}`.trim()}
          style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', alignItems: 'flex-end', gap: tokens.actionGap, minWidth: 0 }}
        >
          {actions}
        </View>
      ) : null}
    </View>
  );
}
