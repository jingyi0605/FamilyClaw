import { GuardedPage, useHouseholdContext, useSetupContext } from '../../../runtime';
import { EmptyState, Section } from '../../family/base';
import { ButlerBootstrapConversation } from '../../setup/ButlerBootstrapConversation';
import { SettingsPageShell } from '../SettingsPageShell';
import { AgentConfigPanel } from '../components/AgentConfigPanel';
import { AiProviderConfigPanel } from '../components/AiProviderConfigPanel';

function mapSetupHint(step: string) {
  if (step === 'family_profile') return '家庭资料';
  if (step === 'first_member') return '首位成员';
  if (step === 'provider_setup') return 'AI 提供商';
  if (step === 'first_butler_agent') return '首个管家 Agent';
  return step;
}

function SettingsAiContent() {
  const { currentHouseholdId } = useHouseholdContext();
  const { setupStatus, refreshSetupStatus } = useSetupContext();

  if (!currentHouseholdId) {
    return (
      <SettingsPageShell activeKey="ai">
        <div className="settings-page">
          <Section title="AI 配置">
            <EmptyState icon="🤖" title="还没有选中家庭" description="先进入一个家庭，再来配 AI。" />
          </Section>
        </div>
      </SettingsPageShell>
    );
  }

  const setupHints = (setupStatus?.missing_requirements ?? []).map(mapSetupHint);
  const needsButlerBootstrap = (setupStatus?.missing_requirements ?? []).includes('first_butler_agent');
  const refreshSetup = async () => {
    await refreshSetupStatus(currentHouseholdId);
  };

  return (
    <SettingsPageShell activeKey="ai">
      <div className="settings-page">
        <Section title="AI 配置">
          {setupHints.length > 0 ? (
            <div className="card setup-resume-card">
              <div className="setup-resume-card__header">
                <div>
                  <h3>这个家庭还有初始化缺口</h3>
                  <p>入口已经正规化了，但坑还在。先把它们补完，别等到对话页反咬你。</p>
                </div>
                <button className="btn btn--outline" type="button" onClick={() => void refreshSetupStatus(currentHouseholdId)}>
                  刷新状态
                </button>
              </div>
              <div className="setup-resume-card__chips">
                {setupHints.map((item) => <span key={item} className="ai-pill">{item}</span>)}
              </div>
            </div>
          ) : null}

          <AiProviderConfigPanel householdId={currentHouseholdId} onChanged={refreshSetup} />
        </Section>

        {needsButlerBootstrap ? (
          <Section title="首个管家引导创建">
            <ButlerBootstrapConversation householdId={currentHouseholdId} onCreated={refreshSetup} />
          </Section>
        ) : null}

        <Section title="Agent 配置中心">
          <AgentConfigPanel householdId={currentHouseholdId} onChanged={refreshSetup} />
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
