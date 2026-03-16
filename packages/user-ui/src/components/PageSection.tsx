import { type CSSProperties, type PropsWithChildren, type ReactNode } from 'react';
import { View } from '@tarojs/components';
import { userAppComponentTokens } from '../theme/tokens';
import { UiCard } from './UiCard';
import { UiText } from './UiText';

type PageSectionProps = PropsWithChildren<{
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
  style?: CSSProperties;
  contentStyle?: CSSProperties;
}>;

export function PageSection({
  title,
  description,
  actions,
  className,
  style,
  contentStyle,
  children,
}: PageSectionProps) {
  const tokens = userAppComponentTokens.pageSection;

  return (
    <UiCard
      className={className}
      style={{
        marginBottom: tokens.marginBottom,
        ...style,
      }}
    >
      <View style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', gap: tokens.descriptionMarginTop }}>
        <View style={{ flex: 1 }}>
          <UiText
            variant="sectionTitle"
            style={{ color: tokens.titleColor, fontSize: tokens.titleFontSize, fontWeight: tokens.titleFontWeight }}
          >
            {title}
          </UiText>
          {description ? (
            <UiText variant="body" style={{ color: tokens.descriptionColor, fontSize: tokens.descriptionFontSize, marginTop: tokens.descriptionMarginTop }}>
              {description}
            </UiText>
          ) : null}
        </View>
        {actions ? (
          <View style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: tokens.descriptionMarginTop }}>
            {actions}
          </View>
        ) : null}
      </View>
      <View style={{ marginTop: tokens.contentMarginTop, ...contentStyle }}>{children}</View>
    </UiCard>
  );
}
