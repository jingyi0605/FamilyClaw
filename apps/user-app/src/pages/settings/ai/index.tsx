import { useEffect, useState } from 'react';
import { GuardedPage, useHouseholdContext, useI18n, useSetupContext } from '../../../runtime';
import { EmptyState, Section } from '../../family/base';
import { SettingsPageShell } from '../SettingsPageShell';
import { AgentConfigPanel } from '../components/AgentConfigPanel';
import { AiProviderConfigPanel } from '../components/AiProviderConfigPanel';

type AiSettingsTab = 'agent' | 'provider';

function pickLocaleText(
  locale: string | undefined,
  values: { zhCN: string; zhTW: string; enUS: string },
) {
  if (locale?.toLowerCase().startsWith('en')) return values.enUS;
  if (locale?.toLowerCase().startsWith('zh-tw')) return values.zhTW;
  return values.zhCN;
}

function mapSetupHint(step: string, locale: string | undefined) {
  if (step === 'family_profile') return pickLocaleText(locale, { zhCN: '家庭资料', zhTW: '家庭資料', enUS: 'Household profile' });
  if (step === 'first_member') return pickLocaleText(locale, { zhCN: '家庭成员', zhTW: '家庭成員', enUS: 'Household members' });
  if (step === 'provider_setup') return pickLocaleText(locale, { zhCN: '模型服务', zhTW: '模型服務', enUS: 'Model providers' });
  if (step === 'first_butler_agent') return pickLocaleText(locale, { zhCN: 'AI 管家', zhTW: 'AI 管家', enUS: 'AI Butler' });
  return step;
}

function pickInitialTab(missingRequirements: string[]): AiSettingsTab {
  if (missingRequirements.includes('provider_setup')) {
    return 'provider';
  }
  return 'agent';
}

function SettingsAiContent() {
  const { locale } = useI18n();
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
        <div className="settings-page">
          <Section title={pickLocaleText(locale, { zhCN: 'AI 设置', zhTW: 'AI 設定', enUS: 'AI settings' })}>
            <EmptyState
              icon="AI"
              title={pickLocaleText(locale, { zhCN: '还没有选中家庭', zhTW: '還沒有選取家庭', enUS: 'No household selected' })}
              description={pickLocaleText(locale, { zhCN: '先选择一个家庭，再来设置 AI。', zhTW: '先選擇一個家庭，再來設定 AI。', enUS: 'Select a household first before configuring AI.' })}
            />
          </Section>
        </div>
      </SettingsPageShell>
    );
  }

  const setupHints = missingRequirements.map(item => mapSetupHint(item, locale));

  async function refreshSetup() {
    await refreshSetupStatus(currentHouseholdId);
  }

  function handleTabChange(nextTab: AiSettingsTab) {
    setTabTouched(true);
    setActiveTab(nextTab);
  }

  return (
    <SettingsPageShell activeKey="ai">
      <div className="settings-page">
        <Section title={pickLocaleText(locale, { zhCN: 'AI 设置', zhTW: 'AI 設定', enUS: 'AI settings' })}>
          {setupHints.length > 0 ? (
            <div className="card setup-resume-card">
              <div className="setup-resume-card__header">
                <div>
                  <h3>{pickLocaleText(locale, { zhCN: '还有几项内容没有设置好', zhTW: '還有幾項內容尚未設定好', enUS: 'A few items still need to be set up' })}</h3>
                  <p>{pickLocaleText(locale, { zhCN: '完成这些内容后，AI 才能更好地为你的家庭提供帮助。', zhTW: '完成這些內容後，AI 才能更好地為您的家庭提供協助。', enUS: 'Once these items are completed, AI can help your household much more effectively.' })}</p>
                </div>
                <button className="btn btn--outline" type="button" onClick={() => void refreshSetup()}>
                  {pickLocaleText(locale, { zhCN: '重新检查', zhTW: '重新檢查', enUS: 'Recheck' })}
                </button>
              </div>
              <div className="setup-resume-card__chips">
                {setupHints.map(item => <span key={item} className="ai-pill">{item}</span>)}
              </div>
            </div>
          ) : null}

          <div className="memory-main-tabs settings-ai-tabs" role="tablist" aria-label={pickLocaleText(locale, { zhCN: 'AI 设置标签', zhTW: 'AI 設定標籤', enUS: 'AI settings tabs' })}>
            <button
              className={`memory-main-tab ${activeTab === 'agent' ? 'memory-main-tab--active' : ''}`}
              type="button"
              role="tab"
              aria-selected={activeTab === 'agent'}
              onClick={() => handleTabChange('agent')}
            >
              {pickLocaleText(locale, { zhCN: 'AI 助手', zhTW: 'AI 助手', enUS: 'AI agents' })}
            </button>
            <button
              className={`memory-main-tab ${activeTab === 'provider' ? 'memory-main-tab--active' : ''}`}
              type="button"
              role="tab"
              aria-selected={activeTab === 'provider'}
              onClick={() => handleTabChange('provider')}
            >
              {pickLocaleText(locale, { zhCN: '模型服务', zhTW: '模型服務', enUS: 'Model providers' })}
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
