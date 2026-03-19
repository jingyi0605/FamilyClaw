/**
 * RN 登录页
 *
 * 品牌区 + 登录表单，简洁温暖的移动端登录体验。
 */
import { useState } from 'react';
import { View, StyleSheet, KeyboardAvoidingView, Platform } from 'react-native';
import Taro from '@tarojs/taro';
import { GuardedPage, useAuthContext, useI18n } from '../../runtime/index.rn';
import {
  RnPageShell,
  RnCard,
  RnText,
  RnButton,
  RnInput,
  RnFormItem,
  rnFoundationTokens,
  rnSemanticTokens,
} from '../../runtime/rn-shell';

function LoginContent() {
  const { login, loginError, loginPending } = useAuthContext();
  const { t } = useI18n();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  async function handleSubmit() {
    try {
      await login(username.trim(), password);
      await Taro.reLaunch({ url: '/pages/entry/index' });
    } catch {
      // 错误已在 loginError 中处理
    }
  }

  const canSubmit = !loginPending && username.trim().length > 0 && password.length > 0;

  return (
    <RnPageShell scrollable={false} safeAreaBottom>
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        {/* 品牌区 */}
        <View style={styles.brandSection}>
          <View style={styles.logoContainer}>
            <View style={styles.logoIcon}>
              <RnText style={styles.logoEmoji}>🐾</RnText>
            </View>
            <RnText variant="title" style={styles.logoText}>FamilyClaw</RnText>
          </View>
          <RnText variant="hero" style={styles.brandTitle}>
            {t('login.brandTitle')}
          </RnText>
          <RnText variant="body" tone="secondary" style={styles.brandDesc}>
            {t('login.brandDesc')}
          </RnText>
        </View>

        {/* 登录表单 */}
        <View style={styles.formSection}>
          <RnCard>
            <View style={styles.formHeader}>
              <RnText variant="title">{t('login.title')}</RnText>
              <RnText variant="caption" tone="secondary" style={styles.formSubtitle}>
                {t('login.formSubtitle')}
              </RnText>
            </View>

            <RnFormItem label={t('login.username')} required>
              <RnInput
                value={username}
                onInput={setUsername}
                placeholder={t('login.usernamePlaceholder')}
                autoCapitalize="none"
                autoCorrect={false}
              />
            </RnFormItem>

            <RnFormItem label={t('login.password')} required>
              <RnInput
                value={password}
                onInput={setPassword}
                placeholder={t('login.passwordPlaceholder')}
                secureTextEntry
              />
            </RnFormItem>

            {loginError ? (
              <View style={styles.errorBox}>
                <RnText variant="caption" tone="danger">{loginError}</RnText>
              </View>
            ) : null}

            <RnButton
              onPress={handleSubmit}
              loading={loginPending}
              disabled={!canSubmit}
              style={styles.submitBtn}
            >
              {loginPending ? t('login.loggingIn') : t('login.submit')}
            </RnButton>
          </RnCard>
        </View>

        {/* 底部说明 */}
        <View style={styles.footer}>
          <RnText variant="caption" tone="tertiary" style={styles.footerText}>
            {t('login.footerHint')}
          </RnText>
        </View>
      </KeyboardAvoidingView>
    </RnPageShell>
  );
}

const styles = StyleSheet.create({
  keyboardView: {
    flex: 1,
  },
  brandSection: {
    paddingHorizontal: rnFoundationTokens.spacing.lg,
    paddingTop: rnFoundationTokens.spacing.xxl,
    paddingBottom: rnFoundationTokens.spacing.lg,
  },
  logoContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: rnFoundationTokens.spacing.md,
  },
  logoIcon: {
    width: 44,
    height: 44,
    borderRadius: rnFoundationTokens.radius.md,
    backgroundColor: rnSemanticTokens.action.primaryLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: rnFoundationTokens.spacing.sm,
  },
  logoEmoji: {
    fontSize: 24,
  },
  logoText: {
    color: rnSemanticTokens.action.primary,
  },
  brandTitle: {
    marginBottom: rnFoundationTokens.spacing.xs,
  },
  brandDesc: {
    lineHeight: 22,
  },
  formSection: {
    flex: 1,
    paddingHorizontal: 0,
  },
  formHeader: {
    alignItems: 'center',
    marginBottom: rnFoundationTokens.spacing.lg,
  },
  formSubtitle: {
    marginTop: rnFoundationTokens.spacing.xs,
  },
  errorBox: {
    backgroundColor: rnSemanticTokens.state.dangerLight,
    borderRadius: rnFoundationTokens.radius.md,
    padding: rnFoundationTokens.spacing.sm,
    marginBottom: rnFoundationTokens.spacing.sm,
  },
  submitBtn: {
    marginTop: rnFoundationTokens.spacing.sm,
  },
  footer: {
    paddingHorizontal: rnFoundationTokens.spacing.lg,
    paddingVertical: rnFoundationTokens.spacing.md,
    alignItems: 'center',
  },
  footerText: {
    textAlign: 'center',
  },
});

export default function LoginPage() {
  return (
    <GuardedPage mode="login" path="/pages/login/index">
      <LoginContent />
    </GuardedPage>
  );
}
