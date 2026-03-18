/**
 * RnPageShell - 页面壳层
 *
 * 提供 SafeAreaView + 可选 ScrollView 的页面容器，
 * 统一背景色和内边距。
 */
import type { ReactNode } from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { rnSemanticTokens, rnFoundationTokens } from '../tokens';

interface RnPageShellProps {
  children: ReactNode;
  /** 是否可滚动，默认 true */
  scrollable?: boolean;
  /** 底部安全区域，默认 true */
  safeAreaBottom?: boolean;
}

export function RnPageShell({
  children,
  scrollable = true,
  safeAreaBottom = true,
}: RnPageShellProps) {
  const content = (
    <View style={styles.inner}>
      {children}
      {safeAreaBottom ? <View style={styles.safeBottom} /> : null}
    </View>
  );

  if (scrollable) {
    return (
      <View style={styles.container}>
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {content}
        </ScrollView>
      </View>
    );
  }

  return <View style={[styles.container, styles.nonScroll]}>{content}</View>;
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: rnSemanticTokens.surface.page,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
  },
  inner: {
    flex: 1,
    paddingHorizontal: rnFoundationTokens.spacing.md,
    paddingTop: rnFoundationTokens.spacing.md,
  },
  nonScroll: {
    flexDirection: 'column',
  },
  safeBottom: {
    height: 34,
  },
});
