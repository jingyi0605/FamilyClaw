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
      }}
    >
      {children}
    </View>
  );
}
