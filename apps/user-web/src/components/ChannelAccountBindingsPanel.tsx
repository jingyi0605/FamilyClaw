/* ============================================================
 * 平台账号成员绑定面板
 * ============================================================ */
import { useEffect, useState, useMemo } from 'react';
import { api, ApiError } from '../lib/api';
import type {
  MemberChannelBindingRead,
  MemberChannelBindingCreate,
  MemberChannelBindingUpdate,
  Member,
} from '../lib/types';

type ChannelAccountBindingsPanelProps = {
  householdId: string;
  accountId: string;
  members: Member[];
};

export function ChannelAccountBindingsPanel({
  householdId,
  accountId,
  members,
}: ChannelAccountBindingsPanelProps) {
  const [bindings, setBindings] = useState<MemberChannelBindingRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  // 弹窗状态
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

  // 成员映射
  const memberMap = useMemo(
    () => new Map(members.map(m => [m.id, m])),
    [members],
  );

  // 加载绑定列表
  useEffect(() => {
    if (!householdId || !accountId) {
      setBindings([]);
      return;
    }

    let cancelled = false;

    const loadBindings = async () => {
      setLoading(true);
      setError('');
      try {
        const result = await api.listChannelAccountBindings(householdId, accountId);
        if (!cancelled) {
          setBindings(result);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载绑定失败');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadBindings();

    return () => {
      cancelled = true;
    };
  }, [householdId, accountId]);

  // 打开新增弹窗
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

  // 打开编辑弹窗
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

  // 保存绑定
  async function handleSaveBinding(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!householdId || !accountId) return;

    setModalLoading(true);
    setFormError('');

    try {
      if (editingBinding) {
        // 编辑模式
        const payload: MemberChannelBindingUpdate = {
          external_user_id: form.external_user_id.trim() || undefined,
          external_chat_id: form.external_chat_id.trim() || null,
          display_hint: form.display_hint.trim() || null,
          binding_status: form.binding_status,
        };
        const result = await api.updateChannelAccountBinding(householdId, accountId, editingBinding.id, payload);
        setBindings(current => current.map(b => (b.id === result.id ? result : b)));
        setStatus('绑定已更新。');
      } else {
        // 新增模式
        if (!form.member_id) {
          setFormError('请选择要绑定的家庭成员。');
          setModalLoading(false);
          return;
        }
        if (!form.external_user_id.trim()) {
          setFormError('请填写外部用户 ID。');
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
        const result = await api.createChannelAccountBinding(householdId, accountId, payload);
        setBindings(current => [result, ...current]);
        setStatus('绑定已创建。');
      }
      setModalOpen(false);
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

  // 停用/恢复绑定
  async function handleToggleBinding(binding: MemberChannelBindingRead) {
    if (!householdId || !accountId) return;

    setLoading(true);
    setError('');
    const newStatus = binding.binding_status === 'disabled' ? 'active' : 'disabled';
    try {
      const result = await api.updateChannelAccountBinding(householdId, accountId, binding.id, {
        binding_status: newStatus,
      });
      setBindings(current => current.map(b => (b.id === result.id ? result : b)));
      setStatus(newStatus === 'active' ? '绑定已恢复。' : '绑定已停用。');
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : '操作失败');
    } finally {
      setLoading(false);
    }
  }

  function formatTimestamp(ts: string): string {
    try {
      return new Date(ts).toLocaleString('zh-CN');
    } catch {
      return ts;
    }
  }

  return (
    <div className="channel-bindings-panel">
      {/* 状态提示 */}
      {error && <div className="settings-note"><span>⚠️</span> {error}</div>}
      {status && <div className="settings-note"><span>✅</span> {status}</div>}

      {/* 绑定列表 */}
      {loading && bindings.length === 0 ? (
        <div className="text-text-secondary">加载绑定中...</div>
      ) : bindings.length === 0 ? (
        <div className="channel-bindings-empty">
          <p>还没有绑定成员。</p>
          <button className="btn btn--primary btn--sm" onClick={openCreateModal}>
            新增绑定
          </button>
        </div>
      ) : (
        <>
          <div className="channel-bindings-header">
            <span>已绑定 {bindings.length} 个成员</span>
            <button className="btn btn--primary btn--sm" onClick={openCreateModal}>
              新增绑定
            </button>
          </div>

          <div className="channel-bindings-list">
            {bindings.map(binding => {
              const member = memberMap.get(binding.member_id);
              const isActive = binding.binding_status === 'active';

              return (
                <div key={binding.id} className={`channel-binding-item ${!isActive ? 'channel-binding-item--disabled' : ''}`}>
                  <div className="channel-binding-item__info">
                    <span className="channel-binding-item__member">
                      {member?.name ?? '未知成员'}
                    </span>
                    <span className="channel-binding-item__external">
                      外部 ID：{binding.external_user_id}
                      {binding.external_chat_id && ` · 会话：${binding.external_chat_id}`}
                    </span>
                    {binding.display_hint && (
                      <span className="channel-binding-item__hint">{binding.display_hint}</span>
                    )}
                  </div>
                  <div className="channel-binding-item__meta">
                    <span className={`badge badge--${isActive ? 'success' : 'secondary'}`}>
                      {isActive ? '生效中' : '已停用'}
                    </span>
                    <span className="channel-binding-item__time">
                      {formatTimestamp(binding.updated_at)}
                    </span>
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

      {/* 新增/编辑绑定弹窗 */}
      {modalOpen && (
        <div className="member-modal-overlay" onClick={() => setModalOpen(false)}>
          <div className="member-modal" onClick={e => e.stopPropagation()}>
            <div className="member-modal__header">
              <h3>{editingBinding ? '编辑成员绑定' : '新增成员绑定'}</h3>
              <p>将平台用户 ID 绑定到家庭成员，让系统识别消息来源。</p>
            </div>
            <form className="settings-form" onSubmit={handleSaveBinding}>
              <div className="form-group">
                <label>家庭成员</label>
                <select
                  className="form-select"
                  value={form.member_id}
                  onChange={e => setForm(f => ({ ...f, member_id: e.target.value }))}
                  disabled={!!editingBinding}
                  required
                >
                  <option value="">请选择成员</option>
                  {members.map(m => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.role})
                    </option>
                  ))}
                </select>
                {!editingBinding && (
                  <div className="form-help">选择后，该成员在此平台发送的消息会被识别。</div>
                )}
              </div>
              <div className="form-group">
                <label>外部用户 ID</label>
                <input
                  className="form-input"
                  value={form.external_user_id}
                  onChange={e => setForm(f => ({ ...f, external_user_id: e.target.value }))}
                  placeholder="例如：telegram:123456789"
                  required
                />
                <div className="form-help">平台上的用户唯一标识，如 Telegram 的 user_id。</div>
              </div>
              <div className="form-group">
                <label>外部会话 ID（可选）</label>
                <input
                  className="form-input"
                  value={form.external_chat_id}
                  onChange={e => setForm(f => ({ ...f, external_chat_id: e.target.value }))}
                  placeholder="例如：-1001234567890"
                />
                <div className="form-help">群聊时使用，用于区分不同会话。</div>
              </div>
              <div className="form-group">
                <label>备注（可选）</label>
                <input
                  className="form-input"
                  value={form.display_hint}
                  onChange={e => setForm(f => ({ ...f, display_hint: e.target.value }))}
                  placeholder="例如：妈妈私人号"
                />
                <div className="form-help">帮助管理员识别这个绑定的用途。</div>
              </div>
              <div className="form-group">
                <label>状态</label>
                <select
                  className="form-select"
                  value={form.binding_status}
                  onChange={e => setForm(f => ({ ...f, binding_status: e.target.value as 'active' | 'disabled' }))}
                >
                  <option value="active">生效</option>
                  <option value="disabled">停用</option>
                </select>
              </div>

              {formError && <div className="settings-note"><span>⚠️</span> {formError}</div>}

              <div className="member-modal__actions">
                <button className="btn btn--outline btn--sm" type="button" onClick={() => setModalOpen(false)} disabled={modalLoading}>
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
