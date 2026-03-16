import { useEffect, useMemo, useState } from 'react';
import Taro from '@tarojs/taro';
import { useI18n } from '../../../runtime';
import { ApiError, settingsApi } from '../settingsApi';
import type {
  ChannelBindingCandidateRead,
  Member,
  MemberChannelBindingCreate,
  MemberChannelBindingRead,
  MemberChannelBindingUpdate,
  PluginRegistryItem,
} from '../settingsTypes';

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

function pickLocaleText(
  locale: string | undefined,
  values: { zhCN: string; zhTW: string; enUS: string },
) {
  if (locale?.toLowerCase().startsWith('en')) {
    return values.enUS;
  }
  if (locale?.toLowerCase().startsWith('zh-tw')) {
    return values.zhTW;
  }
  return values.zhCN;
}

function resolveDateLocale(locale: string | undefined) {
  if (locale?.toLowerCase().startsWith('en')) {
    return 'en-US';
  }
  if (locale?.toLowerCase().startsWith('zh-tw')) {
    return 'zh-TW';
  }
  return 'zh-CN';
}

function formatTimestamp(value: string, locale: string | undefined): string {
  try {
    return new Date(value).toLocaleString(resolveDateLocale(locale));
  } catch {
    return value;
  }
}

function formatApiErrorMessage(
  error: ApiError,
  locale: string | undefined,
): string {
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
  return error.message || pickLocaleText(locale, {
    zhCN: '保存绑定失败',
    zhTW: '儲存綁定失敗',
    enUS: 'Failed to save binding',
  });
}

function buildDisplayHint(candidate: ChannelBindingCandidateRead): string {
  const parts = [
    candidate.sender_display_name,
    candidate.username ? `@${candidate.username}` : null,
  ].filter((item): item is string => Boolean(item && item.trim()));
  return parts.join(' ');
}

function resolveBindingLabels(plugin: PluginRegistryItem | null, locale: string | undefined): BindingLabels {
  const bindingUi = plugin?.capabilities.channel?.ui?.binding;
  return {
    identityLabel: bindingUi?.identity_label ?? pickLocaleText(locale, {
      zhCN: '外部用户 ID',
      zhTW: '外部使用者 ID',
      enUS: 'External User ID',
    }),
    identityPlaceholder: bindingUi?.identity_placeholder ?? pickLocaleText(locale, {
      zhCN: '请输入外部平台用户 ID',
      zhTW: '請輸入外部平台使用者 ID',
      enUS: 'Enter the external platform user ID',
    }),
    identityHelpText: bindingUi?.identity_help_text ?? pickLocaleText(locale, {
      zhCN: '平台里的唯一用户标识。',
      zhTW: '平台中的唯一使用者識別。',
      enUS: 'The unique user identifier on that platform.',
    }),
    chatLabel: bindingUi?.chat_label ?? pickLocaleText(locale, {
      zhCN: '外部会话 ID',
      zhTW: '外部會話 ID',
      enUS: 'External Chat ID',
    }),
    chatPlaceholder: bindingUi?.chat_placeholder ?? pickLocaleText(locale, {
      zhCN: '可选，用来排查会话映射',
      zhTW: '可選，用來排查會話映射',
      enUS: 'Optional, useful for checking chat mapping',
    }),
    chatHelpText: bindingUi?.chat_help_text ?? pickLocaleText(locale, {
      zhCN: '可选，群聊或排障时再填。',
      zhTW: '可選，群聊或排障時再填。',
      enUS: 'Optional. Useful for group chats or troubleshooting.',
    }),
    candidateTitle: bindingUi?.candidate_title ?? pickLocaleText(locale, {
      zhCN: '待绑定候选',
      zhTW: '待綁定候選',
      enUS: 'Binding candidates',
    }),
    candidateHelpText: bindingUi?.candidate_help_text ?? pickLocaleText(locale, {
      zhCN: '这里只显示最近发过消息、但还没绑定成员的平台用户。',
      zhTW: '這裡只顯示最近發過訊息、但還沒綁定成員的平台使用者。',
      enUS: 'Only recent platform users who sent messages and are still unbound are shown here.',
    }),
  };
}

export function ChannelAccountBindingsPanel({
  householdId,
  accountId,
  members,
  plugin,
  supportsMemberBinding,
}: ChannelAccountBindingsPanelProps) {
  const { locale } = useI18n();
  const [bindings, setBindings] = useState<MemberChannelBindingRead[]>([]);
  const [candidates, setCandidates] = useState<ChannelBindingCandidateRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [candidateLoading, setCandidateLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingBinding, setEditingBinding] = useState<MemberChannelBindingRead | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [formError, setFormError] = useState('');
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

  const labels = useMemo(() => resolveBindingLabels(plugin, locale), [locale, plugin]);
  const memberMap = useMemo(() => new Map(members.map((member) => [member.id, member])), [members]);

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
        settingsApi.listChannelAccountBindings(householdId, accountId),
        settingsApi.listChannelAccountBindingCandidates(householdId, accountId),
      ]);
      setBindings(bindingResult);
      setCandidates(candidateResult);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : pickLocaleText(locale, {
            zhCN: '加载成员绑定失败',
            zhTW: '載入成員綁定失敗',
            enUS: 'Failed to load member bindings',
          }),
      );
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
    if (!editingBinding && !form.member_id) {
      setFormError(pickLocaleText(locale, {
        zhCN: '请选择要绑定的家庭成员。',
        zhTW: '請選擇要綁定的家庭成員。',
        enUS: 'Select the family member to bind.',
      }));
      return;
    }
    if (!form.external_user_id.trim()) {
      setFormError(pickLocaleText(locale, {
        zhCN: `请填写${labels.identityLabel}。`,
        zhTW: `請填寫${labels.identityLabel}。`,
        enUS: `Fill in ${labels.identityLabel}.`,
      }));
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
        await settingsApi.updateChannelAccountBinding(householdId, accountId, editingBinding.id, payload);
        setStatus(pickLocaleText(locale, {
          zhCN: '成员绑定已更新。',
          zhTW: '成員綁定已更新。',
          enUS: 'Member binding updated.',
        }));
      } else {
        const payload: MemberChannelBindingCreate = {
          channel_account_id: accountId,
          member_id: form.member_id,
          external_user_id: form.external_user_id.trim(),
          external_chat_id: form.external_chat_id.trim() || null,
          display_hint: form.display_hint.trim() || null,
          binding_status: form.binding_status,
        };
        await settingsApi.createChannelAccountBinding(householdId, accountId, payload);
        setStatus(pickLocaleText(locale, {
          zhCN: '成员绑定已创建。',
          zhTW: '成員綁定已建立。',
          enUS: 'Member binding created.',
        }));
      }
      setModalOpen(false);
      await reloadData();
    } catch (saveError) {
      const message =
        saveError instanceof ApiError
          ? formatApiErrorMessage(saveError, locale)
          : saveError instanceof Error
            ? saveError.message
            : pickLocaleText(locale, {
              zhCN: '保存绑定失败',
              zhTW: '儲存綁定失敗',
              enUS: 'Failed to save binding',
            });
      setFormError(message);
    } finally {
      setModalLoading(false);
    }
  }

  async function handleToggleBinding(binding: MemberChannelBindingRead) {
    if (!householdId || !accountId) {
      return;
    }

    const nextStatus = binding.binding_status === 'disabled' ? 'active' : 'disabled';
    setLoading(true);
    setError('');
    try {
      await settingsApi.updateChannelAccountBinding(householdId, accountId, binding.id, {
        binding_status: nextStatus,
      });
      setStatus(pickLocaleText(locale, {
        zhCN: nextStatus === 'active' ? '成员绑定已恢复。' : '成员绑定已停用。',
        zhTW: nextStatus === 'active' ? '成員綁定已恢復。' : '成員綁定已停用。',
        enUS: nextStatus === 'active' ? 'Member binding restored.' : 'Member binding disabled.',
      }));
      await reloadData();
    } catch (toggleError) {
      setError(
        toggleError instanceof Error
          ? toggleError.message
          : pickLocaleText(locale, {
            zhCN: '切换绑定状态失败',
            zhTW: '切換綁定狀態失敗',
            enUS: 'Failed to change binding status',
          }),
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteBinding(binding: MemberChannelBindingRead) {
    if (!householdId || !accountId) {
      return;
    }

    const modalResult = await Taro.showModal({
      title: pickLocaleText(locale, {
        zhCN: '删除绑定',
        zhTW: '刪除綁定',
        enUS: 'Delete Binding',
      }),
      content: pickLocaleText(locale, {
        zhCN: '删除后，这个外部账号会立即解除成员绑定，后续消息将重新进入待绑定流程。确认删除吗？',
        zhTW: '刪除後，這個外部帳號會立刻解除成員綁定，後續訊息將重新進入待綁定流程。確認刪除嗎？',
        enUS: 'Deleting this will immediately remove the member binding. Future messages will go back to the unbound flow. Continue?',
      }),
      confirmText: pickLocaleText(locale, {
        zhCN: '删除',
        zhTW: '刪除',
        enUS: 'Delete',
      }),
      cancelText: pickLocaleText(locale, {
        zhCN: '取消',
        zhTW: '取消',
        enUS: 'Cancel',
      }),
    });
    if (!modalResult.confirm) {
      return;
    }

    setLoading(true);
    setError('');
    try {
      await settingsApi.deleteChannelAccountBinding(householdId, accountId, binding.id);
      setStatus(pickLocaleText(locale, {
        zhCN: '成员绑定已删除。',
        zhTW: '成員綁定已刪除。',
        enUS: 'Member binding deleted.',
      }));
      await reloadData();
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : pickLocaleText(locale, {
            zhCN: '删除成员绑定失败',
            zhTW: '刪除成員綁定失敗',
            enUS: 'Failed to delete member binding',
          }),
      );
    } finally {
      setLoading(false);
    }
  }

  if (!supportsMemberBinding) {
    return (
      <div className="channel-bindings-panel">
        <div className="form-help">
          {pickLocaleText(locale, {
            zhCN: '当前通道只支持收发消息，不支持成员绑定。',
            zhTW: '目前通道只支援收發訊息，不支援成員綁定。',
            enUS: 'This channel supports messaging only and does not support member binding.',
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="channel-bindings-panel">
      {error ? <div className="settings-note settings-note--error"><span>⚠️</span> {error}</div> : null}
      {status ? <div className="settings-note settings-note--success"><span>✓</span> {status}</div> : null}

      <div className="channel-detail-section">
        <h5>{labels.candidateTitle}</h5>
        <div className="form-help">{labels.candidateHelpText}</div>
        {candidateLoading ? (
          <div className="text-text-secondary">
            {pickLocaleText(locale, {
              zhCN: '正在加载候选...',
              zhTW: '正在載入候選...',
              enUS: 'Loading candidates...',
            })}
          </div>
        ) : candidates.length === 0 ? (
          <div className="form-help">
            {pickLocaleText(locale, {
              zhCN: '当前没有待绑定候选。',
              zhTW: '目前沒有待綁定候選。',
              enUS: 'No pending binding candidates right now.',
            })}
          </div>
        ) : (
          <div className="channel-bindings-list">
            {candidates.map((candidate) => (
              <div key={candidate.inbound_event_id} className="channel-binding-item">
                <div className="channel-binding-item__info">
                  <span className="channel-binding-item__member">
                    {labels.identityLabel}: {candidate.external_user_id}
                  </span>
                  {candidate.username ? <span className="channel-binding-item__hint">@{candidate.username}</span> : null}
                  {candidate.sender_display_name ? <span className="channel-binding-item__hint">{candidate.sender_display_name}</span> : null}
                  {candidate.external_chat_id ? (
                    <span className="channel-binding-item__external">
                      {labels.chatLabel}: {candidate.external_chat_id}
                    </span>
                  ) : null}
                  {candidate.last_message_text ? (
                    <span className="channel-binding-item__external">
                      {pickLocaleText(locale, {
                        zhCN: '最近消息',
                        zhTW: '最近訊息',
                        enUS: 'Latest message',
                      })}
                      : {candidate.last_message_text}
                    </span>
                  ) : null}
                </div>
                <div className="channel-binding-item__meta">
                  <span className="badge badge--warning">
                    {pickLocaleText(locale, {
                      zhCN: candidate.chat_type === 'group' ? '群聊' : '私聊',
                      zhTW: candidate.chat_type === 'group' ? '群聊' : '私聊',
                      enUS: candidate.chat_type === 'group' ? 'Group' : 'Direct',
                    })}
                  </span>
                  <span className="channel-binding-item__time">{formatTimestamp(candidate.last_seen_at, locale)}</span>
                </div>
                <div className="channel-binding-item__actions">
                  <button
                    className="btn btn--primary btn--sm"
                    onClick={() => openCreateModal(candidate)}
                    disabled={loading || modalLoading}
                  >
                    {pickLocaleText(locale, {
                      zhCN: '一键绑定',
                      zhTW: '一鍵綁定',
                      enUS: 'Bind now',
                    })}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {loading && bindings.length === 0 ? (
        <div className="text-text-secondary">
          {pickLocaleText(locale, {
            zhCN: '正在加载成员绑定...',
            zhTW: '正在載入成員綁定...',
            enUS: 'Loading member bindings...',
          })}
        </div>
      ) : bindings.length === 0 ? (
        <div className="channel-bindings-empty">
          <p>{pickLocaleText(locale, {
            zhCN: '还没有成员绑定。',
            zhTW: '還沒有成員綁定。',
            enUS: 'No member bindings yet.',
          })}
          </p>
          <button className="btn btn--primary btn--sm" onClick={() => openCreateModal()}>
            {pickLocaleText(locale, {
              zhCN: '新增绑定',
              zhTW: '新增綁定',
              enUS: 'Add binding',
            })}
          </button>
        </div>
      ) : (
        <>
          <div className="channel-bindings-header">
            <span>{pickLocaleText(locale, {
              zhCN: `已绑定 ${bindings.length} 位成员`,
              zhTW: `已綁定 ${bindings.length} 位成員`,
              enUS: `${bindings.length} member bindings`,
            })}
            </span>
            <button className="btn btn--primary btn--sm" onClick={() => openCreateModal()}>
              {pickLocaleText(locale, {
                zhCN: '新增绑定',
                zhTW: '新增綁定',
                enUS: 'Add binding',
              })}
            </button>
          </div>

          <div className="channel-bindings-list">
            {bindings.map((binding) => {
              const member = memberMap.get(binding.member_id);
              const isActive = binding.binding_status === 'active';

              return (
                <div
                  key={binding.id}
                  className={`channel-binding-item ${!isActive ? 'channel-binding-item--disabled' : ''}`}
                >
                  <div className="channel-binding-item__info">
                    <span className="channel-binding-item__member">
                      {member?.name ?? pickLocaleText(locale, {
                        zhCN: '未知成员',
                        zhTW: '未知成員',
                        enUS: 'Unknown member',
                      })}
                    </span>
                    <span className="channel-binding-item__external">
                      {labels.identityLabel}: {binding.external_user_id}
                      {binding.external_chat_id ? ` / ${labels.chatLabel}: ${binding.external_chat_id}` : ''}
                    </span>
                    {binding.display_hint ? <span className="channel-binding-item__hint">{binding.display_hint}</span> : null}
                  </div>
                  <div className="channel-binding-item__meta">
                    <span className={`badge badge--${isActive ? 'success' : 'secondary'}`}>
                      {pickLocaleText(locale, {
                        zhCN: isActive ? '生效中' : '已停用',
                        zhTW: isActive ? '生效中' : '已停用',
                        enUS: isActive ? 'Active' : 'Disabled',
                      })}
                    </span>
                    <span className="channel-binding-item__time">{formatTimestamp(binding.updated_at, locale)}</span>
                  </div>
                  <div className="channel-binding-item__actions">
                    <button className="btn btn--outline btn--sm" onClick={() => openEditModal(binding)} disabled={loading}>
                      {pickLocaleText(locale, {
                        zhCN: '编辑',
                        zhTW: '編輯',
                        enUS: 'Edit',
                      })}
                    </button>
                    <button className="btn btn--outline btn--sm" onClick={() => void handleToggleBinding(binding)} disabled={loading}>
                      {pickLocaleText(locale, {
                        zhCN: isActive ? '停用' : '恢复',
                        zhTW: isActive ? '停用' : '恢復',
                        enUS: isActive ? 'Disable' : 'Restore',
                      })}
                    </button>
                    <button className="btn btn--outline btn--sm" onClick={() => void handleDeleteBinding(binding)} disabled={loading}>
                      {pickLocaleText(locale, {
                        zhCN: '删除',
                        zhTW: '刪除',
                        enUS: 'Delete',
                      })}
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
              <h3>{pickLocaleText(locale, {
                zhCN: editingBinding ? '编辑成员绑定' : '新增成员绑定',
                zhTW: editingBinding ? '編輯成員綁定' : '新增成員綁定',
                enUS: editingBinding ? 'Edit Member Binding' : 'Add Member Binding',
              })}
              </h3>
              <p>{pickLocaleText(locale, {
                zhCN: '把外部聊天账号对应到家庭成员，系统才知道是谁在说话。',
                zhTW: '把外部聊天帳號對應到家庭成員，系統才知道是誰在說話。',
                enUS: 'Bind external chat accounts to family members so the system knows who is speaking.',
              })}
              </p>
            </div>
            <form className="settings-form" onSubmit={handleSaveBinding}>
              <div className="form-group">
                <label>{pickLocaleText(locale, {
                  zhCN: '家庭成员',
                  zhTW: '家庭成員',
                  enUS: 'Family member',
                })}
                </label>
                <select
                  className="form-select"
                  value={form.member_id}
                  onChange={(event) => setForm((current) => ({ ...current, member_id: event.target.value }))}
                  disabled={Boolean(editingBinding)}
                  required
                >
                  <option value="">
                    {pickLocaleText(locale, {
                      zhCN: '请选择成员',
                      zhTW: '請選擇成員',
                      enUS: 'Select a member',
                    })}
                  </option>
                  {members.map((member) => (
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
                  onChange={(event) => setForm((current) => ({ ...current, external_user_id: event.target.value }))}
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
                  onChange={(event) => setForm((current) => ({ ...current, external_chat_id: event.target.value }))}
                  placeholder={labels.chatPlaceholder}
                />
                <div className="form-help">{labels.chatHelpText}</div>
              </div>

              <div className="form-group">
                <label>{pickLocaleText(locale, {
                  zhCN: '备注',
                  zhTW: '備註',
                  enUS: 'Note',
                })}
                </label>
                <input
                  className="form-input"
                  value={form.display_hint}
                  onChange={(event) => setForm((current) => ({ ...current, display_hint: event.target.value }))}
                  placeholder={pickLocaleText(locale, {
                    zhCN: '例如：妈妈的私聊账号',
                    zhTW: '例如：媽媽的私聊帳號',
                    enUS: 'Example: Mom direct account',
                  })}
                />
              </div>

              <div className="form-group">
                <label>{pickLocaleText(locale, {
                  zhCN: '状态',
                  zhTW: '狀態',
                  enUS: 'Status',
                })}
                </label>
                <select
                  className="form-select"
                  value={form.binding_status}
                  onChange={(event) => setForm((current) => ({
                    ...current,
                    binding_status: event.target.value as 'active' | 'disabled',
                  }))}
                >
                  <option value="active">{pickLocaleText(locale, {
                    zhCN: '启用',
                    zhTW: '啟用',
                    enUS: 'Active',
                  })}
                  </option>
                  <option value="disabled">{pickLocaleText(locale, {
                    zhCN: '停用',
                    zhTW: '停用',
                    enUS: 'Disabled',
                  })}
                  </option>
                </select>
              </div>

              {formError ? <div className="settings-note settings-note--error"><span>⚠️</span> {formError}</div> : null}

              <div className="member-modal__actions">
                <button className="btn btn--outline btn--sm" type="button" onClick={() => setModalOpen(false)} disabled={modalLoading}>
                  {pickLocaleText(locale, {
                    zhCN: '取消',
                    zhTW: '取消',
                    enUS: 'Cancel',
                  })}
                </button>
                <button className="btn btn--primary btn--sm" type="submit" disabled={modalLoading}>
                  {modalLoading
                    ? pickLocaleText(locale, {
                      zhCN: '保存中...',
                      zhTW: '儲存中...',
                      enUS: 'Saving...',
                    })
                    : pickLocaleText(locale, {
                      zhCN: '保存',
                      zhTW: '儲存',
                      enUS: 'Save',
                    })}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
