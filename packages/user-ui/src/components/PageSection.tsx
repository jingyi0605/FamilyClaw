import { PropsWithChildren } from 'react';
import { Text, View } from '@tarojs/components';
import { userAppComponentTokens } from '../theme/tokens';

type PageSectionProps = PropsWithChildren<{
  title: string;
  description?: string;
}>;

export function PageSection({ title, description, children }: PageSectionProps) {
  const tokens = userAppComponentTokens.pageSection;

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
      <Text style={{ color: tokens.titleColor, display: 'block', fontSize: tokens.titleFontSize, fontWeight: '600' }}>
        {title}
      </Text>
      {description ? (
        <Text style={{ color: tokens.descriptionColor, display: 'block', fontSize: tokens.descriptionFontSize, marginTop: tokens.descriptionMarginTop }}>
          {description}
        </Text>
      ) : null}
      <View style={{ marginTop: tokens.contentMarginTop }}>{children}</View>
    </View>
  );
}
