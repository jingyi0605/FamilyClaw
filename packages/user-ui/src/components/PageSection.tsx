import { PropsWithChildren } from 'react';
import { View } from '@tarojs/components';
import { userAppComponentTokens } from '../theme/tokens';
import { UiCard } from './UiCard';
import { UiText } from './UiText';

type PageSectionProps = PropsWithChildren<{
  title: string;
  description?: string;
}>;

export function PageSection({ title, description, children }: PageSectionProps) {
  const tokens = userAppComponentTokens.pageSection;

  return (
    <UiCard
      style={{
        marginBottom: tokens.marginBottom,
      }}
    >
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
      <View style={{ marginTop: tokens.contentMarginTop }}>{children}</View>
    </UiCard>
  );
}
