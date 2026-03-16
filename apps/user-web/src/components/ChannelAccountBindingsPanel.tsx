/* ============================================================
 * 平台账号成员绑定面板
 * ============================================================ */
import { useEffect, useMemo, useState } from 'react';
import { api, ApiError } from '../lib/api';
import type {
  ChannelBindingCandidateRead,
  Member,
  MemberChannelBindingCreate,
  MemberChannelBindingRead,
  MemberChannelBindingUpdate,
  PluginRegistryItem,
} from '../lib/types';

type ChannelAccountBindingsPanelProps = {
  householdId: string;
  accountId: string;
  members: Member[];
  plugin: PluginRegistryItem | null;
  supportsMemberBinding: boolean;
};

type BindingLabels = {
  identityLabel: string;
  identityPlaceholder: string;
  identityHelpText: string;
  chatLabel: string;
  chatPlaceholder: string;
  chatHelpText: string;
  candidateTitle: string;
  candidateHelpText: string;
};

function formatTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleString('zh-CN');
  } catch {
    return ts;
  }
}

function buildDisplayHint(candidate: ChannelBindingCandidateRead): string {
  const parts = [candidate.sender_display_name, candidate.username ? `@${candidate.username}` : null]
    .filter((item): item is string => !!item && item.trim().length > 0);
  return parts.join(' ');
}

function resolveBindingLabels(plugin: PluginRegistryItem | null): BindingLabels {
  const bindingUi = plugin?.capabilities.channel?.ui?.binding;
  return {
    identityLabel: bindingUi?.identity_label ?? '外部用户 ID',
    identityPlaceholder: bindingUi?.identity_placeholder ?? '请输入外部平台用户 ID',
    identityHelpText: bindingUi?.identity_help_text ?? '平台上的唯一用户标识。',
    chatLabel: bindingUi?.chat_label ?? '外部会话 ID',
    chatPlaceholder: bindingUi?.chat_placeholder ?? '可选，用于排查会话映射',
    chatHelpText: bindingUi?.chat_help_text ?? '可选，群聊或需要排查时再填写。',
    candidateTitle: bindingUi?.candidate_title ?? '待绑定候选',
    candidateHelpText: bindingUi?.candidate_help_text ?? '这里只显示最近发过消息、但还没有绑定的用户。',
  };
}

export function ChannelAccountBindingsPanel({
  householdId,
  accountId,
  members,
  plugin,
  supportsMemberBinding,
}: ChannelAccountBindingsPanelProps) {
  const [bindings, setBindings] = useState<MemberChannelBindingRead[]>([]);
  const [candidates, setCandidates] = useState<ChannelBindingCandidateRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [candidateLoading, setCandidateLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const [modalOpen, setModalOpen] = useState(false);
  const [editingBinding, setEditingBinding] = useState<MemberChannelBindingRead | null>(null);
  const [form, setForm] = useState<{
    member_id: string;
    external_user_id: string;
    external_chat_id: string;
    display_hint: string;
    binding_status: 'active' | 'disabled';
  }>({
    member_id: '',
    external_user_id: '',
    external_chat_id: '',
    display_hint: '',
    binding_status: 'active',
  });
  const [modalLoading, setModalLoading] = useState(false);
  const [formError, setFormError] = useState('');

  const labels = useMemo(() => resolveBindingLabels(plugin), [plugin]);
  const memberMap = useMemo(() => new Map(members.map(member => [member.id, member])), [members]);

  async function reloadData() {
    if (!householdId || !accountId || !supportsMemberBinding) {
      setBindings([]);
      setCandidates([]);
      return;
    }

    setLoading(true);
    setCandidateLoading(true);
    setError('');
    try {
      const [bindingResult, candidateResult] = await Promise.all([
        api.listChannelAccountBindings(householdId, accountId),
        api.listChannelAccountBindingCandidates(householdId, accountId),
      ]);
      setBindings(bindingResult);
      setCandidates(candidateResult);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '加载绑定数据失败');
    } finally {
      setLoading(false);
      setCandidateLoading(false);
    }
  }

  useEffect(() => {
    void reloadData();
  }, [accountId, householdId, supportsMemberBinding]);

  function openCreateModal(candidate?: ChannelBindingCandidateRead) {
    setEditingBinding(null);
    setForm({
      member_id: '',
      external_user_id: candidate?.external_user_id ?? '',
      external_chat_id: candidate?.external_chat_id ?? '',
      display_hint: candidate ? buildDisplayHint(candidate) : '',
      binding_status: 'active',
    });
    setFormError('');
    setModalOpen(true);
  }

  function openEditModal(binding: MemberChannelBindingRead) {
    setEditingBinding(binding);
    setForm({
      member_id: binding.member_id,
      external_user_id: binding.external_user_id,
      external_chat_id: binding.external_chat_id ?? '',
      display_hint: binding.display_hint ?? '',
      binding_status: binding.binding_status,
    });
    setFormError('');
    setModalOpen(true);
  }

  async function handleSaveBinding(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!householdId || !accountId) {
      return;
    }
    if (!form.member_id && !editingBinding) {
      setFormError('请选择要绑定的家庭成员。');
      return;
    }
    if (!form.external_user_id.trim()) {
      setFormError(`请填写${labels.identityLabel}。`);
      return;
    }

    setModalLoading(true);
    setFormError('');

    try {
      if (editingBinding) {
        const payload: MemberChannelBindingUpdate = {
          external_user_id: form.external_user_id.trim(),
          external_chat_id: form.external_chat_id.trim() || null,
          display_hint: form.display_hint.trim() || null,
          binding_status: form.binding_status,
        };
        await api.updateChannelAccountBinding(householdId, accountId, editingBinding.id, payload);
        setStatus('绑定已更新。');
      } else {
        const payload: MemberChannelBindingCreate = {
          channel_account_id: accountId,
          member_id: form.member_id,
          external_user_id: form.external_user_id.trim(),
          external_chat_id: form.external_chat_id.trim() || null,
          display_hint: form.display_hint.trim() || null,
          binding_status: form.binding_status,
        };
        await api.createChannelAccountBinding(householdId, accountId, payload);
        setStatus('绑定已创建。');
      }
      setModalOpen(false);
      await reloadData();
    } catch (saveError) {
      const errorMessage =
        saveError instanceof ApiError
          ? ((saveError.payload as { detail?: string })?.detail ?? saveError.message)
          : saveError instanceof Error
            ? saveError.message
            : '保存失败';
      setFormError(errorMessage);
    } finally {
      setModalLoading(false);
    }
  }

  async function handleToggleBinding(binding: MemberChannelBindingRead) {
    if (!householdId || !accountId) {
      return;
    }

    setLoading(true);
    setError('');
    const nextStatus = binding.binding_status === 'disabled' ? 'active' : 'disabled';
    try {
      await api.updateChannelAccountBinding(householdId, accountId, binding.id, {
        binding_status: nextStatus,
      });
      setStatus(nextStatus === 'active' ? '绑定已恢复。' : '绑定已停用。');
      await reloadData();
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : '操作失败');
    } finally {
      setLoading(false);
    }
  }

  if (!supportsMemberBinding) {
    return (
      <div className="channel-bindings-panel">
        <div className="form-help">当前通道只支持出站推送，不支持成员绑定。</div>
      </div>
    );
  }

  return (
    <div className="channel-bindings-panel">
      {error && <div className="settings-note"><span>⚠️</span> {error}</div>}
      {status && <div className="settings-note"><span>✅</span> {status}</div>}

      <div className="channel-detail-section">
        <h5>{labels.candidateTitle}</h5>
        <div className="form-help">{labels.candidateHelpText}</div>
        {candidateLoading ? (
          <div className="text-text-secondary">加载候选中...</div>
        ) : candidates.length === 0 ? (
          <div className="form-help">当前没有待绑定候选。</div>
        ) : (
          <div className="channel-bindings-list">
            {candidates.map(candidate => (
              <div key={candidate.inbound_event_id} className="channel-binding-item">
                <div className="channel-binding-item__info">
                  <span className="channel-binding-item__member">
                    {labels.identityLabel}：{candidate.external_user_id}
                  </span>
                  {candidate.username && (
                    <span className="channel-binding-item__hint">@{candidate.username}</span>
                  )}
                  {candidate.sender_display_name && (
                    <span className="channel-binding-item__hint">{candidate.sender_display_name}</span>
                  )}
                  {candidate.external_chat_id && (
                    <span className="channel-binding-item__external">
                      {labels.chatLabel}：{candidate.external_chat_id}
                    </span>
                  )}
                  {candidate.last_message_text && (
                    <span className="channel-binding-item__external">
                      最近消息：{candidate.last_message_text}
                    </span>
                  )}
                </div>
                <div className="channel-binding-item__meta">
                  <span className="badge badge--warning">{candidate.chat_type === 'group' ? '群聊' : '私聊'}</span>
                  <span className="channel-binding-item__time">{formatTimestamp(candidate.last_seen_at)}</span>
                </div>
                <div className="channel-binding-item__actions">
                  <button
                    className="btn btn--primary btn--sm"
                    onClick={() => openCreateModal(candidate)}
                    disabled={loading || modalLoading}
                  >
                    一键绑定
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {loading && bindings.length === 0 ? (
        <div className="text-text-secondary">加载绑定中...</div>
      ) : bindings.length === 0 ? (
        <div className="channel-bindings-empty">
          <p>还没有成员绑定。</p>
          <button className="btn btn--primary btn--sm" onClick={() => openCreateModal()}>
            新增绑定
          </button>
        </div>
      ) : (
        <>
          <div className="channel-bindings-header">
            <span>已绑定 {bindings.length} 个成员</span>
            <button className="btn btn--primary btn--sm" onClick={() => openCreateModal()}>
              新增绑定
            </button>
          </div>

          <div className="channel-bindings-list">
            {bindings.map(binding => {
              const member = memberMap.get(binding.member_id);
              const isActive = binding.binding_status === 'active';

              return (
                <div
                  key={binding.id}
                  className={`channel-binding-item ${!isActive ? 'channel-binding-item--disabled' : ''}`}
                >
                  <div className="channel-binding-item__info">
                    <span className="channel-binding-item__member">{member?.name ?? '未知成员'}</span>
                    <span className="channel-binding-item__external">
                      {labels.identityLabel}：{binding.external_user_id}
                      {binding.external_chat_id ? ` / ${labels.chatLabel}：${binding.external_chat_id}` : ''}
                    </span>
                    {binding.display_hint && (
                      <span className="channel-binding-item__hint">{binding.display_hint}</span>
                    )}
                  </div>
                  <div className="channel-binding-item__meta">
                    <span className={`badge badge--${isActive ? 'success' : 'secondary'}`}>
                      {isActive ? '生效中' : '已停用'}
                    </span>
                    <span className="channel-binding-item__time">{formatTimestamp(binding.updated_at)}</span>
                  </div>
                  <div className="channel-binding-item__actions">
                    <button
                      className="btn btn--outline btn--sm"
                      onClick={() => openEditModal(binding)}
                      disabled={loading}
                    >
                      编辑
                    </button>
                    <button
                      className="btn btn--outline btn--sm"
                      onClick={() => void handleToggleBinding(binding)}
                      disabled={loading}
                    >
                      {isActive ? '停用' : '恢复'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {modalOpen && (
        <div className="member-modal-overlay" onClick={() => setModalOpen(false)}>
          <div className="member-modal" onClick={event => event.stopPropagation()}>
            <div className="member-modal__header">
              <h3>{editingBinding ? '编辑成员绑定' : '新增成员绑定'}</h3>
              <p>绑定文案和候选展示都来自对应插件声明，宿主这里只负责渲染通用 UI。</p>
            </div>
            <form className="settings-form" onSubmit={handleSaveBinding}>
              <div className="form-group">
                <label>家庭成员</label>
                <select
                  className="form-select"
                  value={form.member_id}
                  onChange={event => setForm(current => ({ ...current, member_id: event.target.value }))}
                  disabled={!!editingBinding}
                  required
                >
                  <option value="">请选择成员</option>
                  {members.map(member => (
                    <option key={member.id} value={member.id}>
                      {member.name} ({member.role})
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>{labels.identityLabel}</label>
                <input
                  className="form-input"
                  value={form.external_user_id}
                  onChange={event => setForm(current => ({ ...current, external_user_id: event.target.value }))}
                  placeholder={labels.identityPlaceholder}
                  required
                />
                <div className="form-help">{labels.identityHelpText}</div>
              </div>

              <div className="form-group">
                <label>{labels.chatLabel}</label>
                <input
                  className="form-input"
                  value={form.external_chat_id}
                  onChange={event => setForm(current => ({ ...current, external_chat_id: event.target.value }))}
                  placeholder={labels.chatPlaceholder}
                />
                <div className="form-help">{labels.chatHelpText}</div>
              </div>

              <div className="form-group">
                <label>备注</label>
                <input
                  className="form-input"
                  value={form.display_hint}
                  onChange={event => setForm(current => ({ ...current, display_hint: event.target.value }))}
                  placeholder="例如：妈妈的私聊账号"
                />
                <div className="form-help">帮助管理员快速识别这个绑定的用途。</div>
              </div>

              <div className="form-group">
                <label>状态</label>
                <select
                  className="form-select"
                  value={form.binding_status}
                  onChange={event => setForm(current => ({
                    ...current,
                    binding_status: event.target.value as 'active' | 'disabled',
                  }))}
                >
                  <option value="active">生效</option>
                  <option value="disabled">停用</option>
                </select>
              </div>

              {formError && <div className="settings-note"><span>⚠️</span> {formError}</div>}

              <div className="member-modal__actions">
                <button
                  className="btn btn--outline btn--sm"
                  type="button"
                  onClick={() => setModalOpen(false)}
                  disabled={modalLoading}
                >
                  取消
                </button>
                <button className="btn btn--primary btn--sm" type="submit" disabled={modalLoading}>
                  {modalLoading ? '保存中...' : '保存'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
