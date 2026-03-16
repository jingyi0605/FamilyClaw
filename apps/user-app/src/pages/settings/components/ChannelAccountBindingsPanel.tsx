import { useEffect, useMemo, useState } from 'react';
import { ApiError, settingsApi } from '../settingsApi';
import type {
  Member,
  MemberChannelBindingCreate,
  MemberChannelBindingRead,
  MemberChannelBindingUpdate,
} from '../settingsTypes';

function formatApiErrorMessage(error: ApiError): string {
  const payload = error.payload as { detail?: unknown } | undefined;
  const detail = payload?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== 'object') {
          return null;
        }
        const message = 'msg' in item && typeof item.msg === 'string' ? item.msg : null;
        const location = 'loc' in item && Array.isArray(item.loc)
          ? item.loc
            .filter((part: unknown): part is string | number => typeof part === 'string' || typeof part === 'number')
            .join('.')
          : '';
        if (message && location) {
          return `${location}: ${message}`;
        }
        return message;
      })
      .filter((item): item is string => Boolean(item));
    if (messages.length > 0) {
      return messages.join('；');
    }
  }
  return error.message || '保存失败';
}

export function ChannelAccountBindingsPanel(props: {
  householdId: string;
  accountId: string;
  members: Member[];
}) {
  const { householdId, accountId, members } = props;
  const [bindings, setBindings] = useState<MemberChannelBindingRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingBinding, setEditingBinding] = useState<MemberChannelBindingRead | null>(null);
  const [form, setForm] = useState({
    member_id: '',
    external_user_id: '',
    external_chat_id: '',
    display_hint: '',
    binding_status: 'active' as 'active' | 'disabled',
  });
  const [modalLoading, setModalLoading] = useState(false);
  const [formError, setFormError] = useState('');

  const memberMap = useMemo(() => new Map(members.map((member) => [member.id, member])), [members]);

  useEffect(() => {
    if (!householdId || !accountId) {
      setBindings([]);
      return;
    }

    let cancelled = false;

    async function loadBindings() {
      setLoading(true);
      setError('');
      try {
        const result = await settingsApi.listChannelAccountBindings(householdId, accountId);
        if (!cancelled) {
          setBindings(result);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载成员关联失败');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadBindings();
    return () => {
      cancelled = true;
    };
  }, [accountId, householdId]);

  function openCreateModal() {
    setEditingBinding(null);
    setForm({
      member_id: '',
      external_user_id: '',
      external_chat_id: '',
      display_hint: '',
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

    setModalLoading(true);
    setFormError('');

    try {
      if (editingBinding) {
        const payload: MemberChannelBindingUpdate = {
          external_user_id: form.external_user_id.trim() || undefined,
          external_chat_id: form.external_chat_id.trim() || null,
          display_hint: form.display_hint.trim() || null,
          binding_status: form.binding_status,
        };
        const result = await settingsApi.updateChannelAccountBinding(householdId, accountId, editingBinding.id, payload);
        setBindings((current) => current.map((item) => item.id === result.id ? result : item));
        setStatus('成员关联已更新');
      } else {
        if (!form.member_id) {
          setFormError('请选择要关联的家庭成员');
          setModalLoading(false);
          return;
        }
        if (!form.external_user_id.trim()) {
          setFormError('请填写平台用户 ID');
          setModalLoading(false);
          return;
        }
        const payload: MemberChannelBindingCreate = {
          channel_account_id: accountId,
          member_id: form.member_id,
          external_user_id: form.external_user_id.trim(),
          external_chat_id: form.external_chat_id.trim() || null,
          display_hint: form.display_hint.trim() || null,
          binding_status: form.binding_status,
        };
        const result = await settingsApi.createChannelAccountBinding(householdId, accountId, payload);
        setBindings((current) => [result, ...current]);
        setStatus('成员关联已添加');
      }
      setModalOpen(false);
    } catch (saveError) {
      const errorMessage = saveError instanceof ApiError
        ? formatApiErrorMessage(saveError)
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
      const result = await settingsApi.updateChannelAccountBinding(householdId, accountId, binding.id, {
        binding_status: nextStatus,
      });
      setBindings((current) => current.map((item) => item.id === result.id ? result : item));
      setStatus(nextStatus === 'active' ? '成员关联已恢复' : '成员关联已停用');
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : '操作失败');
    } finally {
      setLoading(false);
    }
  }

  function formatTimestamp(value: string) {
    try {
      return new Date(value).toLocaleString('zh-CN');
    } catch {
      return value;
    }
  }

  return (
    <div className="channel-bindings-panel">
      {error ? <div className="settings-note"><span>⚠️</span> {error}</div> : null}
      {status ? <div className="settings-note"><span>✓</span> {status}</div> : null}

      {loading && bindings.length === 0 ? (
        <div className="text-text-secondary">加载成员关联中...</div>
      ) : bindings.length === 0 ? (
        <div className="channel-bindings-empty">
          <p>还没有关联成员。</p>
          <button className="btn btn--primary btn--sm" onClick={openCreateModal}>添加关联</button>
        </div>
      ) : (
        <>
          <div className="channel-bindings-header">
            <span>已关联 {bindings.length} 位成员</span>
            <button className="btn btn--primary btn--sm" onClick={openCreateModal}>添加关联</button>
          </div>

          <div className="channel-bindings-list">
            {bindings.map((binding) => {
              const member = memberMap.get(binding.member_id);
              const isActive = binding.binding_status === 'active';
              return (
                <div key={binding.id} className={`channel-binding-item ${!isActive ? 'channel-binding-item--disabled' : ''}`}>
                  <div className="channel-binding-item__info">
                    <span className="channel-binding-item__member">{member?.name ?? '未知成员'}</span>
                    <span className="channel-binding-item__external">
                      平台用户 ID：{binding.external_user_id}
                      {binding.external_chat_id ? ` · 聊天窗口：${binding.external_chat_id}` : ''}
                    </span>
                    {binding.display_hint ? <span className="channel-binding-item__hint">{binding.display_hint}</span> : null}
                  </div>
                  <div className="channel-binding-item__meta">
                    <span className={`badge badge--${isActive ? 'success' : 'secondary'}`}>{isActive ? '已生效' : '已停用'}</span>
                    <span className="channel-binding-item__time">{formatTimestamp(binding.updated_at)}</span>
                  </div>
                  <div className="channel-binding-item__actions">
                    <button className="btn btn--outline btn--sm" onClick={() => openEditModal(binding)} disabled={loading}>修改</button>
                    <button className="btn btn--outline btn--sm" onClick={() => void handleToggleBinding(binding)} disabled={loading}>
                      {isActive ? '停用' : '恢复使用'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {modalOpen ? (
        <div className="member-modal-overlay" onClick={() => setModalOpen(false)}>
          <div className="member-modal" onClick={(event) => event.stopPropagation()}>
            <div className="member-modal__header">
              <h3>{editingBinding ? '修改成员关联' : '添加成员关联'}</h3>
              <p>把聊天平台上的账号和家庭成员对应起来，系统才知道是谁在发消息。</p>
            </div>
            <form className="settings-form" onSubmit={handleSaveBinding}>
              <div className="form-group">
                <label>家庭成员</label>
                <select
                  className="form-select"
                  value={form.member_id}
                  onChange={(event) => setForm((current) => ({ ...current, member_id: event.target.value }))}
                  disabled={Boolean(editingBinding)}
                  required
                >
                  <option value="">请选择成员</option>
                  {members.map((member) => (
                    <option key={member.id} value={member.id}>{member.name} ({member.role})</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>平台用户 ID</label>
                <input
                  className="form-input"
                  value={form.external_user_id}
                  onChange={(event) => setForm((current) => ({ ...current, external_user_id: event.target.value }))}
                  placeholder="例如：telegram:123456789"
                  required
                />
              </div>
              <div className="form-group">
                <label>聊天窗口 ID（可选）</label>
                <input
                  className="form-input"
                  value={form.external_chat_id}
                  onChange={(event) => setForm((current) => ({ ...current, external_chat_id: event.target.value }))}
                  placeholder="例如：-1001234567890"
                />
              </div>
              <div className="form-group">
                <label>备注名称（可选）</label>
                <input
                  className="form-input"
                  value={form.display_hint}
                  onChange={(event) => setForm((current) => ({ ...current, display_hint: event.target.value }))}
                  placeholder="例如：妈妈私人号"
                />
              </div>
              <div className="form-group">
                <label>状态</label>
                <select
                  className="form-select"
                  value={form.binding_status}
                  onChange={(event) => setForm((current) => ({ ...current, binding_status: event.target.value as 'active' | 'disabled' }))}
                >
                  <option value="active">生效</option>
                  <option value="disabled">停用</option>
                </select>
              </div>

              {formError ? <div className="settings-note"><span>⚠️</span> {formError}</div> : null}

              <div className="member-modal__actions">
                <button className="btn btn--outline btn--sm" type="button" onClick={() => setModalOpen(false)} disabled={modalLoading}>取消</button>
                <button className="btn btn--primary btn--sm" type="submit" disabled={modalLoading}>{modalLoading ? '保存中...' : '保存'}</button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
