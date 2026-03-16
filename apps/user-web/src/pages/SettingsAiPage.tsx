import { useEffect, useState } from 'react';
import { Card, EmptyState, Section } from '../components/base';
import { AiProviderConfigPanel } from '../components/AiProviderConfigPanel';
import { AgentConfigPanel } from '../components/AgentConfigPanel';
import { useI18n } from '../i18n';
import { useHouseholdContext } from '../state/household';
import { useSetupContext } from '../state/setup';

type AiSettingsTab = 'agent' | 'provider';

function mapSetupHint(step: string) {
  if (step === 'family_profile') {
    return '家庭资料';
  }
  if (step === 'first_member') {
    return '家庭成员';
  }
  if (step === 'provider_setup') {
    return '模型服务';
  }
  if (step === 'first_butler_agent') {
    return 'AI 管家';
  }
  return step;
}

function pickInitialTab(missingRequirements: string[]): AiSettingsTab {
  if (missingRequirements.includes('provider_setup')) {
    return 'provider';
  }
  return 'agent';
}

export function SettingsAiPage() {
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
      <div className="settings-page">
        <Section title={t('settings.ai')}>
          <EmptyState icon="AI" title="还没有选中家庭" description="先选择一个家庭，再来设置 AI。" />
        </Section>
      </div>
    );
  }

  const setupHints = missingRequirements.map(mapSetupHint);

  async function refreshSetup() {
    await refreshSetupStatus(currentHouseholdId);
  }

  function handleTabChange(nextTab: AiSettingsTab) {
    setTabTouched(true);
    setActiveTab(nextTab);
  }

  return (
    <div className="settings-page">
      <Section title={t('settings.ai')}>
        {setupHints.length > 0 && (
          <Card className="setup-resume-card">
            <div className="setup-resume-card__header">
              <div>
                <h3>还有几项内容没有设置好</h3>
                <p>完成这些内容后，AI 才能更好地为你的家庭提供帮助。</p>
              </div>
              <button className="btn btn--outline" type="button" onClick={() => void refreshSetup()}>
                重新检查
              </button>
            </div>
            <div className="setup-resume-card__chips">
              {setupHints.map(item => <span key={item} className="ai-pill">{item}</span>)}
            </div>
          </Card>
        )}

        <div className="memory-main-tabs settings-ai-tabs" role="tablist" aria-label="AI 设置标签">
          <button
            className={`memory-main-tab ${activeTab === 'agent' ? 'memory-main-tab--active' : ''}`}
            type="button"
            role="tab"
            aria-selected={activeTab === 'agent'}
            onClick={() => handleTabChange('agent')}
          >
            AI 助手
          </button>
          <button
            className={`memory-main-tab ${activeTab === 'provider' ? 'memory-main-tab--active' : ''}`}
            type="button"
            role="tab"
            aria-selected={activeTab === 'provider'}
            onClick={() => handleTabChange('provider')}
          >
            模型服务
          </button>
        </div>

        <div className="settings-ai-tab-panel">
          {activeTab === 'agent' ? (
            <AgentConfigPanel householdId={currentHouseholdId} onChanged={refreshSetup} />
          ) : (
            <AiProviderConfigPanel householdId={currentHouseholdId} onChanged={refreshSetup} />
          )}
        </div>
      </Section>
    </div>
  );
}
