import { PropsWithChildren } from 'react';
import { Text, View } from '@tarojs/components';
import { userAppTokens } from '../theme/tokens';

type PageSectionProps = PropsWithChildren<{
  title: string;
  description?: string;
}>;

export function PageSection({ title, description, children }: PageSectionProps) {
  return (
    <View
      style={{
        background: userAppTokens.colorSurface,
        border: `1px solid ${userAppTokens.colorBorder}`,
        borderRadius: userAppTokens.radiusLg,
        marginBottom: userAppTokens.spacingSm,
        padding: userAppTokens.spacingMd,
      }}
    >
      <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '32px', fontWeight: '600' }}>
        {title}
      </Text>
      {description ? (
        <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '24px', marginTop: '8px' }}>
          {description}
        </Text>
      ) : null}
      <View style={{ marginTop: userAppTokens.spacingSm }}>{children}</View>
    </View>
  );
}
