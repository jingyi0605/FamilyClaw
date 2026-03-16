import { PropsWithChildren } from 'react';
import { PageSection, StatusCard, UiCard, UiText, userAppTokens } from '@familyclaw/user-ui';
import { AppShellPage } from './AppShellPage';
import { useAppRuntime, from '../runtime';
import { useI18n } from '../runtime';

type AuthShellPageProps = PropsWithChildren<{
  title: string;
  description: string;
}>;

export function AuthShellPage({ title, description, children }: AuthShellPageProps) {
  const { bootstrap, error, refreshing } = useAppRuntime();
  const { t } = useI18n();

  return (
    <AppShellPage>
      <UiCard
        style={{
          background: `linear-gradient(160deg, ${userAppTokens.colorPrimary} 0%, #0f9d6c 100%)`,
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
      >
        <UiText variant="title" tone="inverse" style={{ fontSize: '40px', fontWeight: '700' }}>
          FamilyClaw
        </UiText>
        <UiText variant="body" tone="inverse" style={{ color: 'rgba(255,255,255,0.88)', fontSize: '26px' }}>
          {t('authShell.loading.description')}
        </UiText>
      </UiCard>

      <PageSection title={title} description={description}>
        <StatusCard
          label={t('authShell.status.currentPlatform')}
          value={bootstrap ? `${bootstrap.platformTarget.platform} / ${bootstrap.platformTarget.runtime}` : t('common.loading')}
          tone="info"
        />
        <StatusCard
          label={t('authShell.status.accountStatus')}
          value={bootstrap?.actor?.authenticated ? t('authShell.status.loggedIn', { username: bootstrap.actor.username }) : t('common.notLoggedIn')}
          tone={bootstrap?.actor?.authenticated ? 'success' : 'warning'}
        />
        {refreshing ? <UiText variant="body" tone="secondary" style={{ fontSize: '24px' }}>{t('authShell.refreshing')}</UiText> : null}
        {error ? <UiText variant="body" tone="warning" style={{ fontSize: '24px' }}>{error}</UiText> : null}
      </PageSection>

      {children}
    </AppShellPage>
  );
}
