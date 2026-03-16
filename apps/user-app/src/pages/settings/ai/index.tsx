import { useEffect, useState } from 'react';
import { EmptyStateCard, PageSection, UiCard, UiButton, UiTag } from '@familyclaw/user-ui';
import { GuardedPage, useHouseholdContext, useI18n, useSetupContext } from '../../../runtime';
import { SettingsPageShell } from '../SettingsPageShell';
import { AgentConfigPanel } from '../components/AgentConfigPanel';
import { AiProviderConfigPanel } from '../components/AiProviderConfigPanel';

type AiSettingsTab = 'agent' | 'provider';

function getRequestedTab(): AiSettingsTab | null {
  if (typeof window === 'undefined') {
    return null;
  }

  const tab = new URLSearchParams(window.location.search).get('tab');
  return tab === 'agent' || tab === 'provider' ? tab : null;
}

function mapSetupHint(step: string, t: (key: string) => string) {
  if (step === 'family_profile') return t('settings.ai.hint.familyProfile');
  if (step === 'first_member') return t('settings.ai.hint.firstMember');
  if (step === 'provider_setup') return t('settings.ai.hint.providerSetup');
  if (step === 'first_butler_agent') return t('settings.ai.hint.firstButler');
  return step;
}

function pickInitialTab(_: string[]): AiSettingsTab {
  return getRequestedTab() ?? 'provider';
}

function SettingsAiContent() {
  const { t } = useI18n();
  const { currentHouseholdId } = useHouseholdContext();
  const { setupStatus, refreshSetupStatus } = useSetupContext();
  const missingRequirements = setupStatus?.missing_requirements ?? [];
  const [activeTab, setActiveTab] = useState<AiSettingsTab>(() => pickInitialTab(missingRequirements));
  const [tabTouched, setTabTouched] = useState(false);

  useEffect(() => {
    setTabTouched(false);
  }, [currentHouseholdId]);

  useEffect(() => {
    if (!tabTouched) {
      setActiveTab(pickInitialTab(missingRequirements));
    }
  }, [missingRequirements, tabTouched]);

  if (!currentHouseholdId) {
    return (
      <SettingsPageShell activeKey="ai">
        <div className="settings-page settings-page--ai">
          <PageSection title={t('settings.ai.title')} contentStyle={{ marginTop: 0 }}>
            <EmptyStateCard
              icon="AI"
              title={t('settings.ai.emptyHousehold')}
              description={t('settings.ai.emptyHouseholdHint')}
            />
          </PageSection>
        </div>
      </SettingsPageShell>
    );
  }

  const setupHints = missingRequirements.map(item => mapSetupHint(item, t));

  async function refreshSetup() {
    await refreshSetupStatus(currentHouseholdId);
  }

  function handleTabChange(nextTab: AiSettingsTab) {
    setTabTouched(true);
    setActiveTab(nextTab);
  }

  return (
    <SettingsPageShell activeKey="ai">
      <div className="settings-page settings-page--ai">
        <PageSection title={t('settings.ai.title')} contentStyle={{ marginTop: 0 }}>
          {setupHints.length > 0 ? (
            <UiCard className="setup-resume-card">
              <div className="setup-resume-card__header">
                <div>
                  <h3>{t('settings.ai.setupResume.title')}</h3>
                  <p>{t('settings.ai.setupResume.desc')}</p>
                </div>
                <UiButton variant="secondary" size="sm" onClick={() => void refreshSetup()}>
                  {t('settings.ai.setupResume.recheck')}
                </UiButton>
              </div>
              <div className="setup-resume-card__chips">
                {setupHints.map(item => <UiTag key={item} variant="info" label={item} />)}
              </div>
            </UiCard>
          ) : null}

          <div className="memory-main-tabs settings-ai-tabs" role="tablist" aria-label={t('settings.ai.tabs')}>
            <button
              className={`memory-main-tab ${activeTab === 'provider' ? 'memory-main-tab--active' : ''}`}
              type="button"
              role="tab"
              aria-selected={activeTab === 'provider'}
              onClick={() => handleTabChange('provider')}
            >
              {t('settings.ai.tab.provider')}
            </button>
            <button
              className={`memory-main-tab ${activeTab === 'agent' ? 'memory-main-tab--active' : ''}`}
              type="button"
              role="tab"
              aria-selected={activeTab === 'agent'}
              onClick={() => handleTabChange('agent')}
            >
              {t('settings.ai.tab.agent')}
            </button>
          </div>

          <div className="settings-ai-tab-panel">
            {activeTab === 'provider' ? (
              <AiProviderConfigPanel householdId={currentHouseholdId} onChanged={refreshSetup} />
            ) : (
              <AgentConfigPanel householdId={currentHouseholdId} onChanged={refreshSetup} />
            )}
          </div>
        </PageSection>
      </div>
    </SettingsPageShell>
  );
}

export default function SettingsAiPage() {
  return (
    <GuardedPage mode="protected" path="/pages/settings/ai/index">
      <SettingsAiContent />
    </GuardedPage>
  );
}
