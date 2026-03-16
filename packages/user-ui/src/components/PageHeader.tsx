import { View } from '@tarojs/components';
import { type CSSProperties, type ReactNode } from 'react';
import { userAppComponentTokens } from '../theme/tokens';
import { UiText } from './UiText';

type PageHeaderProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
  style?: CSSProperties;
};

export function PageHeader({ title, description, actions, className, style }: PageHeaderProps) {
  const tokens = userAppComponentTokens.pageHeader;

  return (
    <View
      className={className}
      style={{
        display: 'flex',
        flexDirection: 'row',
        flexWrap: 'wrap',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: tokens.gap,
        marginBottom: tokens.marginBottom,
        ...style,
      }}
    >
      <View style={{ display: 'flex', flexDirection: 'column', gap: tokens.titleGap, flex: 1 }}>
        <UiText variant="title" style={{ fontSize: tokens.titleFontSize }}>
          {title}
        </UiText>
        {description ? (
          <UiText tone="secondary" style={{ color: tokens.descriptionColor, fontSize: tokens.descriptionFontSize }}>
            {description}
          </UiText>
        ) : null}
      </View>
      {actions ? (
        <View style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: tokens.actionGap }}>
          {actions}
        </View>
      ) : null}
    </View>
  );
}
