import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Card } from './base';
import { api } from '../lib/api';
import {
  assignProviderFormValue,
  AI_CAPABILITY_OPTIONS,
  buildCreateProviderPayload,
  buildProviderFormState,
  buildRoutePayload,
  buildUpdateProviderPayload,
  getCapabilityLabel,
  getProviderAdapterCode,
  getProviderModelName,
  readProviderFormValue,
  toProviderFormState,
} from '../lib/aiConfig';
import type { AiCapabilityRoute, AiProviderAdapter, AiProviderProfile } from '../lib/types';

type Props = {
  householdId: string;
  compact?: boolean;
  capabilityFilter?: string[];
  onChanged?: () => Promise<void> | void;
};

type ProviderFormState = ReturnType<typeof buildProviderFormState>;

export function AiProviderConfigPanel({ householdId, compact = false, capabilityFilter, onChanged }: Props) {
  const [adapters, setAdapters] = useState<AiProviderAdapter[]>([]);
  const [providers, setProviders] = useState<AiProviderProfile[]>([]);
  const [routes, setRoutes] = useState<AiCapabilityRoute[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState('');
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const [form, setForm] = useState<ProviderFormState>(buildProviderFormState());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const visibleCapabilities = useMemo(
    () => capabilityFilter ?? AI_CAPABILITY_OPTIONS.map(item => item.value),
    [capabilityFilter],
  );
  const currentAdapter = useMemo(
    () => adapters.find(item => item.adapter_code === form.adapterCode) ?? null,
    [adapters, form.adapterCode],
  );
  const selectedProvider = useMemo(
    () => providers.find(item => item.id === selectedProviderId) ?? null,
    [providers, selectedProviderId],
  );

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const [adapterRows, providerRows, routeRows] = await Promise.all([
          api.listAiProviderAdapters(),
          api.listHouseholdAiProviders(householdId),
          api.listHouseholdAiRoutes(householdId),
        ]);
        if (cancelled) {
          return;
        }
        setAdapters(adapterRows);
        setProviders(providerRows);
        setRoutes(routeRows);
        setSelectedProviderId(current => (providerRows.some(item => item.id === current) ? current : (providerRows[0]?.id ?? '')));
        if (!editingProviderId) {
          setForm(current => current.adapterCode ? current : buildProviderFormState(adapterRows[0] ?? null));
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '加载供应商配置失败');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [editingProviderId, householdId]);

  function startCreate() {
    setEditingProviderId(null);
    setStatus('');
    setError('');
    setForm(buildProviderFormState(adapters[0] ?? null));
  }

  function startEdit(provider: AiProviderProfile) {
    const adapter = adapters.find(item => item.adapter_code === getProviderAdapterCode(provider)) ?? adapters[0] ?? null;
    setEditingProviderId(provider.id);
    setSelectedProviderId(provider.id);
    setStatus('');
    setError('');
    setForm(toProviderFormState(provider, adapter));
  }

  async function reload() {
    const [providerRows, routeRows] = await Promise.all([
      api.listHouseholdAiProviders(householdId),
      api.listHouseholdAiRoutes(householdId),
    ]);
    setProviders(providerRows);
    setRoutes(routeRows);
    await onChanged?.();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentAdapter) {
      setError('请先选择供应商类型');
      return;
    }
    setSaving(true);
    setError('');
    setStatus('');
    try {
      if (editingProviderId) {
        await api.updateHouseholdAiProvider(householdId, editingProviderId, buildUpdateProviderPayload(form, currentAdapter));
        setStatus('供应商配置已更新。');
      } else {
        const created = await api.createHouseholdAiProvider(householdId, buildCreateProviderPayload(form, currentAdapter));
        setEditingProviderId(created.id);
        setSelectedProviderId(created.id);
        setStatus('供应商配置已创建。');
      }
      await reload();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存供应商配置失败');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selectedProvider) {
      return;
    }
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await api.deleteHouseholdAiProvider(householdId, selectedProvider.id);
      setEditingProviderId(null);
      setSelectedProviderId('');
      setForm(buildProviderFormState(adapters[0] ?? null));
      setStatus('供应商配置已删除。');
      await reload();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : '删除供应商配置失败');
    } finally {
      setSaving(false);
    }
  }

  async function bindProviderToCapability(capability: string, providerId: string, enabled: boolean) {
    setSaving(true);
    setError('');
    setStatus('');
    try {
      const currentRoute = routes.find(item => item.capability === capability);
      await api.upsertHouseholdAiRoute(
        householdId,
        capability,
        buildRoutePayload(householdId, capability, currentRoute, providerId || null, enabled),
      );
      setStatus(`${getCapabilityLabel(capability)} 路由已更新。`);
      await reload();
    } catch (routeError) {
      setError(routeError instanceof Error ? routeError.message : '更新能力路由失败');
    } finally {
      setSaving(false);
    }
  }

  const providerCards = providers.filter(item => !compact || visibleCapabilities.some(capability => item.supported_capabilities.includes(capability)));

  return (
    <div className="ai-provider-center">
      <div className="ai-provider-center__toolbar">
        <button className="btn btn--primary" type="button" onClick={startCreate}>新增供应商</button>
        {selectedProvider && <button className="btn btn--outline" type="button" onClick={() => startEdit(selectedProvider)}>编辑当前供应商</button>}
        {selectedProvider && !compact && <button className="btn btn--outline" type="button" onClick={() => void handleDelete()} disabled={saving}>删除当前供应商</button>}
      </div>
      {loading && <Card><p>正在读取供应商配置…</p></Card>}
      {error && <Card><p className="form-error">{error}</p></Card>}
      {!loading && (
        <>
          <div className="ai-config-list">
            {providerCards.length === 0 && (
              <Card className="ai-config-card">
                <p className="ai-config-muted">当前家庭还没有可用供应商。先建一个，再谈什么正式入口。</p>
              </Card>
            )}
            {providerCards.map(provider => (
              <button
                key={provider.id}
                type="button"
                className={`ai-config-card ${selectedProviderId === provider.id ? 'ai-config-card--selected' : ''}`}
                onClick={() => setSelectedProviderId(provider.id)}
              >
                <div className="ai-config-card__top">
                  <div className="ai-config-card__text">
                    <div className="ai-config-card__title-row">
                      <h3>{provider.display_name}</h3>
                      <span className={`ai-pill ${provider.enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>{provider.enabled ? '已启用' : '已停用'}</span>
                    </div>
                    <p className="ai-config-card__meta">{provider.provider_code}</p>
                    <p className="ai-config-card__summary">{getProviderModelName(provider) ?? '未填写模型名'}</p>
                  </div>
                </div>
                <div className="ai-config-chip-list">
                  {provider.supported_capabilities.map(capability => <span key={capability} className="ai-pill">{getCapabilityLabel(capability)}</span>)}
                </div>
              </button>
            ))}
          </div>

          <Card className="ai-config-detail-card">
            <div className="setup-step-panel__header">
              <div>
                <h3>{editingProviderId ? '编辑供应商配置' : '新增供应商配置'}</h3>
                <p>页面按适配器定义渲染，不继续把每家供应商的差异散落在向导里。</p>
              </div>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label htmlFor={`provider-adapter-${householdId}`}>供应商类型</label>
                <select
                  id={`provider-adapter-${householdId}`}
                  className="form-select"
                  value={form.adapterCode}
                  onChange={event => setForm(buildProviderFormState(adapters.find(item => item.adapter_code === event.target.value) ?? null))}
                  disabled={Boolean(editingProviderId)}
                >
                  <option value="">请选择</option>
                  {adapters.map(adapter => <option key={adapter.adapter_code} value={adapter.adapter_code}>{adapter.display_name}</option>)}
                </select>
              </div>
              {currentAdapter && (
                <>
                  <p className="ai-config-muted">{currentAdapter.description}</p>
                  <div className="setup-form-grid">
                    {currentAdapter.field_schema.map(field => (
                      <div key={field.key} className="form-group">
                        <label htmlFor={`${householdId}-${field.key}`}>{field.label}</label>
                        {field.field_type === 'select' ? (
                          <select
                            id={`${householdId}-${field.key}`}
                            className="form-select"
                            value={readFieldValue(form, field.key)}
                            onChange={event => setForm(current => assignFieldValue(current, field.key, event.target.value))}
                          >
                            <option value="">请选择</option>
                            {field.options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                          </select>
                        ) : (
                          <input
                            id={`${householdId}-${field.key}`}
                            className="form-input"
                            type={field.field_type === 'number' ? 'number' : 'text'}
                            value={readFieldValue(form, field.key)}
                            onChange={event => setForm(current => assignFieldValue(current, field.key, event.target.value))}
                            placeholder={field.placeholder ?? undefined}
                            disabled={Boolean(editingProviderId && field.key === 'provider_code')}
                          />
                        )}
                        {field.help_text && <p className="ai-config-muted">{field.help_text}</p>}
                      </div>
                    ))}
                    <div className="form-group">
                      <label>支持能力</label>
                      <div className="setup-choice-group">
                        {AI_CAPABILITY_OPTIONS.map(item => (
                          <label key={item.value} className="setup-choice">
                            <input
                              type="checkbox"
                              checked={form.supportedCapabilities.includes(item.value)}
                              onChange={() => {
                                setForm(current => ({
                                  ...current,
                                  supportedCapabilities: current.supportedCapabilities.includes(item.value)
                                    ? current.supportedCapabilities.filter(capability => capability !== item.value)
                                    : [...current.supportedCapabilities, item.value],
                                }));
                              }}
                            />
                            <span>{item.label}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                    <div className="form-group">
                      <label className="setup-choice">
                        <input
                          type="checkbox"
                          checked={form.enabled}
                          onChange={event => setForm(current => ({ ...current, enabled: event.target.checked }))}
                        />
                        <span>保存后立即启用</span>
                      </label>
                    </div>
                  </div>
                </>
              )}
              {status && <div className="setup-form-status">{status}</div>}
              <div className="setup-form-actions">
                <button
                  className="btn btn--primary"
                  type="submit"
                  disabled={saving || !currentAdapter || !form.displayName.trim() || !form.providerCode.trim() || !form.modelName.trim() || form.supportedCapabilities.length === 0}
                >
                  {saving ? '保存中…' : editingProviderId ? '保存供应商' : '创建供应商'}
                </button>
              </div>
            </form>
          </Card>

          <Card className="ai-config-detail-card">
            <div className="setup-step-panel__header">
              <div>
                <h3>{compact ? '向导所需能力路由' : '能力路由绑定'}</h3>
                <p>{compact ? '这里只绑定向导真正会用到的能力。' : '真正影响对话主链路的是这里，不是上面那张好看的卡片。'}</p>
              </div>
            </div>
            <div className="ai-route-grid">
              {visibleCapabilities.map(capability => {
                const route = routes.find(item => item.capability === capability);
                const candidates = providers.filter(item => item.enabled && item.supported_capabilities.includes(capability));
                return (
                  <div key={capability} className="ai-route-card">
                    <div className="ai-route-card__top">
                      <strong>{getCapabilityLabel(capability)}</strong>
                      <span className={`ai-pill ${route?.enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>{route?.enabled ? '已启用' : '未启用'}</span>
                    </div>
                    <div className="form-group">
                      <label htmlFor={`${householdId}-route-${capability}`}>主供应商</label>
                      <select
                        id={`${householdId}-route-${capability}`}
                        className="form-select"
                        value={route?.primary_provider_profile_id ?? ''}
                        onChange={event => void bindProviderToCapability(capability, event.target.value, Boolean(event.target.value))}
                      >
                        <option value="">未绑定</option>
                        {candidates.map(provider => <option key={provider.id} value={provider.id}>{provider.display_name}</option>)}
                      </select>
                    </div>
                    <button
                      type="button"
                      className="btn btn--outline"
                      onClick={() => void bindProviderToCapability(capability, route?.primary_provider_profile_id ?? '', !route?.enabled)}
                      disabled={!route?.primary_provider_profile_id}
                    >
                      {route?.enabled ? '停用路由' : '启用路由'}
                    </button>
                  </div>
                );
              })}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function readFieldValue(form: ProviderFormState, fieldKey: string) {
  return readProviderFormValue(form, fieldKey);
}

function assignFieldValue(form: ProviderFormState, fieldKey: string, value: string): ProviderFormState {
  return assignProviderFormValue(form, fieldKey, value);
}
