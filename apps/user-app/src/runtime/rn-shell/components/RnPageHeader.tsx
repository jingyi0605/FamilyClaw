/**
 * RnPageHeader - 页面标题
 */
import { View, StyleSheet } from 'react-native';
import { rnFoundationTokens } from '../tokens';
import { RnText } from './RnText';

interface RnPageHeaderProps {
  title: string;
  description?: string;
}

export function RnPageHeader({ title, description }: RnPageHeaderProps) {
  return (
    <View style={styles.container}>
      <RnText variant="hero">{title}</RnText>
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
    marginBottom: rnFoundationTokens.spacing.md,
  },
  description: {
    marginTop: rnFoundationTokens.spacing.xs,
  },
});
