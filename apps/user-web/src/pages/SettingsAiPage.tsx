/* ============================================================
 * AI 配置页 - 展示多 Agent 列表和只读详情
 * ============================================================ */
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState, Card, Section } from '../components/base';
import { useI18n } from '../i18n';
import { api } from '../lib/api';
import { getAgentStatusLabel, getAgentTypeEmoji, getAgentTypeLabel } from '../lib/agents';
import type { AgentDetail, AgentSummary, Member } from '../lib/types';
import { useHouseholdContext } from '../state/household';
import { useSetupContext } from '../state/setup';

export function SettingsAiPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { currentHouseholdId } = useHouseholdContext();
  const { setupStatus } = useSetupContext();
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!currentHouseholdId) {
      setAgents([]);
      setMembers([]);
      setSelectedAgentId('');
      setDetail(null);
      return;
    }

    let cancelled = false;

    const loadOverview = async () => {
      setLoading(true);
      setError('');
      try {
        const [agentResponse, memberResponse] = await Promise.all([
          api.listAgents(currentHouseholdId),
          api.listMembers(currentHouseholdId),
        ]);

        if (cancelled) {
          return;
        }

        setAgents(agentResponse.items);
        setMembers(memberResponse.items);
        setSelectedAgentId(current =>
          agentResponse.items.some(item => item.id === current) ? current : (agentResponse.items[0]?.id ?? ''),
        );
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载 AI 配置失败');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadOverview();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId]);

  useEffect(() => {
    if (!currentHouseholdId || !selectedAgentId) {
      setDetail(null);
      return;
    }

    let cancelled = false;

    const loadDetail = async () => {
      setDetailLoading(true);
      setError('');
      try {
        const result = await api.getAgentDetail(currentHouseholdId, selectedAgentId);
        if (!cancelled) {
          setDetail(result);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载 Agent 详情失败');
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    };

    void loadDetail();

    return () => {
      cancelled = true;
    };
  }, [currentHouseholdId, selectedAgentId]);

  const selectedSummary = useMemo(
    () => agents.find(item => item.id === selectedAgentId) ?? null,
    [agents, selectedAgentId],
  );
  const memberNameMap = useMemo(
    () => new Map(members.map(member => [member.id, member.name])),
    [members],
  );
  const setupHints = useMemo(() => {
    if (!setupStatus || setupStatus.is_required || setupStatus.missing_requirements.length === 0) {
      return [];
    }
    const labels: Record<string, string> = {
      family_profile: '家庭资料',
      first_member: '首位成员',
      provider_setup: 'AI 供应商',
      first_butler_agent: '首个管家 Agent',
      finish: '完成放行',
    };
    return setupStatus.missing_requirements.map(step => labels[step] ?? step);
  }, [setupStatus]);

  if (!currentHouseholdId) {
    return (
      <div className="settings-page">
        <Section title={t('settings.ai')}>
          <EmptyState icon="🤖" title={t('settings.ai.empty')} description={t('settings.ai.emptyHint')} />
        </Section>
      </div>
    );
  }

  return (
    <div className="settings-page">
      <Section title={t('settings.ai')}>
        {setupHints.length > 0 && (
          <Card className="setup-resume-card">
            <div className="setup-resume-card__header">
              <div>
                <h3>这个家庭还有补录项</h3>
                <p>现在不强制锁你，但这些缺口还在。拖着不补，后面照样反咬你。</p>
              </div>
              <button className="btn btn--outline" type="button" onClick={() => navigate('/setup')}>
                去补录
              </button>
            </div>
            <div className="setup-resume-card__chips">
              {setupHints.map(item => (
                <span key={item} className="ai-pill">{item}</span>
              ))}
            </div>
          </Card>
        )}
        <div className="settings-note">
          <span>ℹ️</span> {t('settings.ai.overviewNote')}
        </div>
        <div className="settings-note">
          <span>🛠️</span> {t('settings.ai.advancedNote')}
        </div>

        {error && (
          <div className="settings-note">
            <span>⚠️</span> {error}
          </div>
        )}

        {loading && agents.length === 0 ? (
          <div className="settings-note">
            <span>⏳</span> {t('common.loading')}
          </div>
        ) : agents.length === 0 ? (
          <EmptyState icon="🤖" title={t('settings.ai.empty')} description={t('settings.ai.emptyHint')} />
        ) : (
          <>
            <div className="ai-config-list">
              {agents.map(agent => (
                <Card
                  key={agent.id}
                  className={`ai-config-card ${agent.id === selectedAgentId ? 'ai-config-card--selected' : ''}`}
                  onClick={() => setSelectedAgentId(agent.id)}
                >
                  <div className="ai-config-card__top">
                    <div className="ai-config-card__avatar">{getAgentTypeEmoji(agent.agent_type)}</div>
                    <div className="ai-config-card__text">
                      <div className="ai-config-card__title-row">
                        <strong>{agent.display_name}</strong>
                        {agent.default_entry && <span className="ai-pill ai-pill--primary">{t('settings.ai.defaultEntry')}</span>}
                        {agent.is_primary && !agent.default_entry && <span className="ai-pill">{t('settings.ai.primaryAgent')}</span>}
                      </div>
                      <span className="ai-config-card__meta">
                        {getAgentTypeLabel(agent.agent_type)} · {getAgentStatusLabel(agent.status)}
                      </span>
                    </div>
                  </div>
                  <p className="ai-config-card__summary">{agent.summary ?? t('settings.ai.noSummary')}</p>
                  <div className="ai-config-card__footer">
                    <span className={`ai-pill ${agent.conversation_enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>
                      {agent.conversation_enabled ? t('settings.ai.canConversation') : t('settings.ai.noConversation')}
                    </span>
                  </div>
                </Card>
              ))}
            </div>

            <Section
              title={t('settings.ai.detailTitle')}
              className="section--embedded"
              actions={selectedSummary?.conversation_enabled ? (
                <button className="btn btn--outline" type="button" onClick={() => navigate('/conversation')}>
                  {t('settings.ai.openConversation')}
                </button>
              ) : undefined}
            >
              {detailLoading ? (
                <div className="settings-note">
                  <span>⏳</span> {t('common.loading')}
                </div>
              ) : !detail ? (
                <EmptyState icon="🧩" title={t('settings.ai.detailEmpty')} description={t('settings.ai.detailEmptyHint')} />
              ) : (
                <div className="ai-config-detail">
                  <div className="ai-config-detail__hero">
                    <div className="ai-config-detail__avatar">{getAgentTypeEmoji(detail.agent_type)}</div>
                    <div className="ai-config-detail__text">
                      <div className="ai-config-detail__title-row">
                        <h3>{detail.display_name}</h3>
                        <span className="ai-pill">{getAgentTypeLabel(detail.agent_type)}</span>
                        <span className="ai-pill">{getAgentStatusLabel(detail.status)}</span>
                      </div>
                      <p>{detail.soul?.role_summary ?? detail.soul?.self_identity ?? selectedSummary?.summary ?? t('settings.ai.noSummary')}</p>
                    </div>
                  </div>

                  <div className="ai-config-detail__grid">
                    <Card className="ai-config-detail-card">
                      <h4>{t('settings.ai.roleCard')}</h4>
                      <p>{detail.soul?.self_identity ?? t('settings.ai.noSelfIdentity')}</p>
                      {detail.soul?.intro_message && (
                        <div className="ai-config-detail-card__block">
                          <strong>{t('settings.ai.introMessage')}</strong>
                          <span>{detail.soul.intro_message}</span>
                        </div>
                      )}
                      {detail.soul?.speaking_style && (
                        <div className="ai-config-detail-card__block">
                          <strong>{t('settings.ai.speakingStyle')}</strong>
                          <span>{detail.soul.speaking_style}</span>
                        </div>
                      )}
                    </Card>

                    <Card className="ai-config-detail-card">
                      <h4>{t('settings.ai.runtimeCard')}</h4>
                      <div className="ai-config-chip-list">
                        <span className={`ai-pill ${detail.runtime_policy?.default_entry ? 'ai-pill--primary' : 'ai-pill--muted'}`}>
                          {detail.runtime_policy?.default_entry ? t('settings.ai.defaultEntry') : t('settings.ai.nonDefaultEntry')}
                        </span>
                        <span className={`ai-pill ${detail.runtime_policy?.conversation_enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>
                          {detail.runtime_policy?.conversation_enabled ? t('settings.ai.canConversation') : t('settings.ai.noConversation')}
                        </span>
                      </div>
                      <div className="ai-config-detail-card__block">
                        <strong>{t('settings.ai.routingTags')}</strong>
                        <div className="ai-config-chip-list">
                          {(detail.runtime_policy?.routing_tags ?? []).length > 0 ? (
                            detail.runtime_policy?.routing_tags.map(tag => <span key={tag} className="ai-pill">{tag}</span>)
                          ) : (
                            <span className="ai-config-muted">{t('settings.ai.noRoutingTags')}</span>
                          )}
                        </div>
                      </div>
                    </Card>

                    <Card className="ai-config-detail-card">
                      <h4>{t('settings.ai.personalityCard')}</h4>
                      <div className="ai-config-detail-card__block">
                        <strong>{t('settings.ai.personalityTraits')}</strong>
                        <div className="ai-config-chip-list">
                          {(detail.soul?.personality_traits ?? []).length > 0 ? (
                            detail.soul?.personality_traits.map(item => <span key={item} className="ai-pill">{item}</span>)
                          ) : (
                            <span className="ai-config-muted">{t('settings.ai.noTraits')}</span>
                          )}
                        </div>
                      </div>
                      <div className="ai-config-detail-card__block">
                        <strong>{t('settings.ai.serviceFocus')}</strong>
                        <div className="ai-config-chip-list">
                          {(detail.soul?.service_focus ?? []).length > 0 ? (
                            detail.soul?.service_focus.map(item => <span key={item} className="ai-pill">{item}</span>)
                          ) : (
                            <span className="ai-config-muted">{t('settings.ai.noServiceFocus')}</span>
                          )}
                        </div>
                      </div>
                    </Card>

                    <Card className="ai-config-detail-card">
                      <h4>{t('settings.ai.cognitionCard')}</h4>
                      {(detail.member_cognitions ?? []).length > 0 ? (
                        <div className="ai-cognition-list">
                          {detail.member_cognitions.map(item => (
                            <div key={item.id} className="ai-cognition-item">
                              <div className="ai-cognition-item__top">
                                <strong>{memberNameMap.get(item.member_id) ?? item.member_id}</strong>
                                <span>{item.display_address ?? t('settings.ai.defaultAddress')}</span>
                              </div>
                              <div className="ai-cognition-item__meta">
                                <span>{t('settings.ai.closeness')}{item.closeness_level}</span>
                                <span>{t('settings.ai.priority')}{item.service_priority}</span>
                              </div>
                              {item.communication_style && <p>{item.communication_style}</p>}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="ai-config-muted">{t('settings.ai.noCognitions')}</div>
                      )}
                    </Card>
                  </div>
                </div>
              )}
            </Section>
          </>
        )}
      </Section>
    </div>
  );
}
