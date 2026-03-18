/**
 * RnEmptyState - 空状态提示
 */
import { View, StyleSheet } from 'react-native';
import { rnSemanticTokens, rnFoundationTokens } from '../tokens';
import { RnText } from './RnText';

interface RnEmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
}

export function RnEmptyState({ icon, title, description }: RnEmptyStateProps) {
  return (
    <View style={styles.container}>
      {icon ? <RnText variant="hero" style={styles.icon}>{icon}</RnText> : null}
      <RnText variant="title" style={styles.title}>{title}</RnText>
      {description ? (
        <RnText variant="body" tone="secondary" style={styles.description}>
          {description}
        </RnText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: rnSemanticTokens.action.primaryLight,
    borderColor: rnSemanticTokens.border.default,
    borderWidth: 1,
    borderRadius: rnFoundationTokens.radius.lg,
    padding: rnFoundationTokens.spacing.xl,
    alignItems: 'center',
    marginVertical: rnFoundationTokens.spacing.md,
  },
  icon: {
    marginBottom: rnFoundationTokens.spacing.sm,
  },
  title: {
    textAlign: 'center',
    marginBottom: rnFoundationTokens.spacing.xs,
  },
  description: {
    textAlign: 'center',
  },
});
