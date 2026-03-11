import { Card, EmptyState, Section } from '../components/base';
import { AiProviderConfigPanel } from '../components/AiProviderConfigPanel';
import { AgentConfigPanel } from '../components/AgentConfigPanel';
import { ButlerBootstrapConversation } from '../components/ButlerBootstrapConversation';
import { useI18n } from '../i18n';
import { useHouseholdContext } from '../state/household';
import { useSetupContext } from '../state/setup';

export function SettingsAiPage() {
  const { t } = useI18n();
  const { currentHouseholdId } = useHouseholdContext();
  const { setupStatus, refreshSetupStatus } = useSetupContext();

  if (!currentHouseholdId) {
    return (
      <div className="settings-page">
        <Section title={t('settings.ai')}>
          <EmptyState icon="🤖" title={t('settings.ai.empty')} description={t('settings.ai.emptyHint')} />
        </Section>
      </div>
    );
  }

  const setupHints = (setupStatus?.missing_requirements ?? []).map(step => {
    if (step === 'family_profile') {
      return '家庭资料';
    }
    if (step === 'first_member') {
      return '首位成员';
    }
    if (step === 'provider_setup') {
      return 'AI 供应商';
    }
    if (step === 'first_butler_agent') {
      return '首个管家 Agent';
    }
    return step;
  });
  const needsButlerBootstrap = (setupStatus?.missing_requirements ?? []).includes('first_butler_agent');

  return (
    <div className="settings-page">
      <Section title={t('settings.ai')}>
        {setupHints.length > 0 && (
          <Card className="setup-resume-card">
            <div className="setup-resume-card__header">
              <div>
                <h3>这个家庭还有初始化缺口</h3>
                <p>现在入口已经正规化了，但没配完的坑还在。先把它们补平，别等到对话页反咬你。</p>
              </div>
              <button className="btn btn--outline" type="button" onClick={() => void refreshSetupStatus(currentHouseholdId)}>
                刷新状态
              </button>
            </div>
            <div className="setup-resume-card__chips">
              {setupHints.map(item => <span key={item} className="ai-pill">{item}</span>)}
            </div>
          </Card>
        )}

        <AiProviderConfigPanel householdId={currentHouseholdId} onChanged={() => void refreshSetupStatus(currentHouseholdId)} />
      </Section>

      {needsButlerBootstrap && (
        <Section title="首个管家引导创建">
          <ButlerBootstrapConversation
            householdId={currentHouseholdId}
            onCreated={() => void refreshSetupStatus(currentHouseholdId)}
          />
        </Section>
      )}

      <Section title="Agent 配置中心">
        <AgentConfigPanel householdId={currentHouseholdId} onChanged={() => void refreshSetupStatus(currentHouseholdId)} />
      </Section>
    </div>
  );
}
