import { Pressable, StyleSheet, View } from 'react-native';
import { useI18n } from '../../h5-shell/index.rn';
import type { UserGuideOverlayProps } from '../../shared/user-guide/GuideOverlay.types';
import { RnText } from '../components/RnText';
import { rnFoundationTokens, rnSemanticTokens } from '../tokens';

export function GuideOverlay(props: UserGuideOverlayProps) {
  const { t } = useI18n();
  const isBusy = props.status === 'waiting_anchor' || props.status === 'completing' || props.isActionPending;

  return (
    <View pointerEvents="box-none" style={styles.overlay}>
      <View style={styles.card}>
        <View style={styles.header}>
          <View style={styles.badge}>
            <RnText variant="caption" tone="primary">
              {t('userGuide.badge')}
            </RnText>
          </View>
          <RnText variant="caption" tone="secondary">
            {t('userGuide.progress', {
              current: props.currentStepIndex + 1,
              total: props.totalSteps,
            })}
          </RnText>
        </View>

        <RnText variant="title" style={styles.title}>
          {props.title}
        </RnText>
        <RnText variant="body" tone="secondary">
          {props.content}
        </RnText>

        {isBusy ? (
          <RnText variant="caption" tone="warning" style={styles.status}>
            {props.status === 'completing' || props.isActionPending
              ? t('userGuide.status.completing')
              : t('userGuide.status.locating')}
          </RnText>
        ) : null}

        {props.errorMessage ? (
          <RnText variant="caption" tone="danger" style={styles.status}>
            {props.errorMessage}
          </RnText>
        ) : null}

        <View style={styles.actions}>
          <Pressable disabled={isBusy} onPress={() => props.onSkip()}>
            <RnText variant="body" tone="secondary">
              {t('userGuide.actions.skip')}
            </RnText>
          </Pressable>

          <View style={styles.actionsRight}>
            <Pressable
              disabled={props.currentStepIndex === 0 || isBusy}
              onPress={() => props.onPrevious()}
              style={[styles.secondaryButton, (props.currentStepIndex === 0 || isBusy) ? styles.buttonDisabled : null]}
            >
              <RnText variant="caption" tone="secondary">
                {t('userGuide.actions.previous')}
              </RnText>
            </Pressable>
            <Pressable
              disabled={isBusy}
              onPress={() => (props.isLastStep ? props.onFinish() : props.onNext())}
              style={[styles.primaryButton, styles.primaryButtonSpacing, isBusy ? styles.buttonDisabled : null]}
            >
              <RnText variant="caption" style={styles.primaryButtonText}>
                {props.isLastStep ? t('userGuide.actions.finish') : t('userGuide.actions.next')}
              </RnText>
            </Pressable>
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'flex-end',
    paddingHorizontal: rnFoundationTokens.spacing.md,
    paddingBottom: rnFoundationTokens.spacing.lg,
  },
  card: {
    backgroundColor: 'rgba(255, 250, 245, 0.98)',
    borderRadius: rnFoundationTokens.radius.lg,
    borderWidth: 1,
    borderColor: 'rgba(245, 138, 58, 0.18)',
    padding: rnFoundationTokens.spacing.md,
    shadowColor: '#1f1726',
    shadowOpacity: 0.12,
    shadowOffset: { width: 0, height: 10 },
    shadowRadius: 18,
    elevation: 8,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: rnFoundationTokens.spacing.sm,
  },
  badge: {
    paddingHorizontal: rnFoundationTokens.spacing.sm,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: rnSemanticTokens.action.primaryLight,
  },
  title: {
    marginBottom: rnFoundationTokens.spacing.xs,
  },
  status: {
    marginTop: rnFoundationTokens.spacing.sm,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: rnFoundationTokens.spacing.md,
  },
  actionsRight: {
    flexDirection: 'row',
  },
  secondaryButton: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: rnSemanticTokens.border.subtle,
    paddingHorizontal: rnFoundationTokens.spacing.md,
    paddingVertical: rnFoundationTokens.spacing.sm,
    backgroundColor: rnSemanticTokens.surface.card,
  },
  primaryButton: {
    borderRadius: 999,
    paddingHorizontal: rnFoundationTokens.spacing.md,
    paddingVertical: rnFoundationTokens.spacing.sm,
    backgroundColor: rnSemanticTokens.action.primary,
  },
  primaryButtonSpacing: {
    marginLeft: rnFoundationTokens.spacing.sm,
  },
  primaryButtonText: {
    color: '#fff9f2',
    fontWeight: '700',
  },
  buttonDisabled: {
    opacity: 0.45,
  },
});
