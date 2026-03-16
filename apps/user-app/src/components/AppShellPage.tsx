import { PropsWithChildren } from 'react';
import { View } from '@tarojs/components';
import { userAppTokens } from '@familyclaw/user-ui';

export function AppShellPage({ children }: PropsWithChildren) {
  return (
    <View
      style={{
        minHeight: '100vh',
        background: userAppTokens.colorBg,
        padding: userAppTokens.spacingSm,
        paddingBottom: userAppTokens.spacingXl,
      }}
    >
      <View style={{ display: 'flex', flexDirection: 'column', gap: userAppTokens.spacingSm }}>
        {children}
      </View>
    </View>
  );
}
