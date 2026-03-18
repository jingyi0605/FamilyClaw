/**
 * RnSection - 分区卡片
 *
 * 带标题的内容区域，常用于设置页和首页分组。
 */
import type { ReactNode } from 'react';
import { View, StyleSheet } from 'react-native';
import { rnSemanticTokens, rnFoundationTokens, rnComponentTokens } from '../tokens';
import { RnText } from './RnText';

interface RnSectionProps {
  title: string;
  description?: string;
  children: ReactNode;
}

export function RnSection({ title, description, children }: RnSectionProps) {
  return (
    <View style={[styles.container, rnComponentTokens.shadow.sm]}>
      <RnText variant="title" style={styles.title}>{title}</RnText>
      {description ? (
        <RnText variant="body" tone="secondary" style={styles.description}>
          {description}
        </RnText>
      ) : null}
      <View style={styles.content}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: rnSemanticTokens.surface.card,
    borderColor: rnSemanticTokens.border.subtle,
    borderWidth: 1,
    borderRadius: rnFoundationTokens.radius.lg,
    padding: rnFoundationTokens.spacing.md,
    marginBottom: rnFoundationTokens.spacing.sm,
  },
  title: {
    marginBottom: rnFoundationTokens.spacing.xs,
  },
  description: {
    marginTop: rnFoundationTokens.spacing.xs,
  },
  content: {
    marginTop: rnFoundationTokens.spacing.sm,
  },
});
