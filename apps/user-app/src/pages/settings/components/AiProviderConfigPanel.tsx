import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Card } from '../../family/base';
import {
  AI_CAPABILITY_OPTIONS,
  assignProviderFormValue,
  buildCreateProviderPayload,
  buildProviderFormState,
  buildRoutePayload,
  buildUpdateProviderPayload,
  getCapabilityLabel,
  getProviderAdapterCode,
  getProviderModelName,
  readProviderFormValue,
  toProviderFormState,
} from '../../setup/setupAiConfig';
import { settingsApi } from '../settingsApi';
import type { AiCapabilityRoute, AiProviderAdapter, AiProviderProfile } from '../settingsTypes';

type ProviderFormState = ReturnType<typeof buildProviderFormState>;

export function AiProviderConfigPanel(props: {
  householdId: string;
  compact?: boolean;
  capabilityFilter?: string[];
  onChanged?: () => Promise<void> | void;
}) {
  const { householdId, compact = false, capabilityFilter, onChanged } = props;
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
    () => capabilityFilter ?? AI_CAPABILITY_OPTIONS.map((item) => item.value),
    [capabilityFilter],
  );
  const currentAdapter = useMemo(
    () => adapters.find((item) => item.adapter_code === form.adapterCode) ?? null,
    [adapters, form.adapterCode],
  );
  const selectedProvider = useMemo(
    () => providers.find((item) => item.id === selectedProviderId) ?? null,
    [providers, selectedProviderId],
  );

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const [adapterRows, providerRows, routeRows] = await Promise.all([
          settingsApi.listAiProviderAdapters(),
          settingsApi.listHouseholdAiProviders(householdId),
          settingsApi.listHouseholdAiRoutes(householdId),
        ]);
        if (cancelled) {
          return;
        }
        setAdapters(adapterRows);
        setProviders(providerRows);
        setRoutes(routeRows);
        setSelectedProviderId((current) => (
          providerRows.some((item) => item.id === current) ? current : (providerRows[0]?.id ?? '')
        ));
        if (!editingProviderId) {
          setForm((current) => current.adapterCode ? current : buildProviderFormState(adapterRows[0] ?? null));
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : '?? AI ???????');
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
    const adapter = adapters.find((item) => item.adapter_code === getProviderAdapterCode(provider)) ?? adapters[0] ?? null;
    setEditingProviderId(provider.id);
    setSelectedProviderId(provider.id);
    setStatus('');
    setError('');
    setForm(toProviderFormState(provider, adapter));
  }

  async function reload() {
    const [providerRows, routeRows] = await Promise.all([
      settingsApi.listHouseholdAiProviders(householdId),
      settingsApi.listHouseholdAiRoutes(householdId),
    ]);
    setProviders(providerRows);
    setRoutes(routeRows);
    await onChanged?.();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentAdapter) {
      setError('?????????');
      return;
    }
    setSaving(true);
    setError('');
    setStatus('');
    try {
      if (editingProviderId) {
        await settingsApi.updateHouseholdAiProvider(
          householdId,
          editingProviderId,
          buildUpdateProviderPayload(form, currentAdapter),
        );
        setStatus('鎻愪緵鍟嗛厤缃凡鏇存柊');
      } else {
        const created = await settingsApi.createHouseholdAiProvider(
          householdId,
          buildCreateProviderPayload(form, currentAdapter),
        );
        setEditingProviderId(created.id);
        setSelectedProviderId(created.id);
        setStatus('鎻愪緵鍟嗛厤缃凡鍒涘缓');
      }
      await reload();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '?????????');
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
      await settingsApi.deleteHouseholdAiProvider(householdId, selectedProvider.id);
      setEditingProviderId(null);
      setSelectedProviderId('');
      setForm(buildProviderFormState(adapters[0] ?? null));
      setStatus('鎻愪緵鍟嗛厤缃凡鍒犻櫎');
      await reload();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : '?????????');
    } finally {
      setSaving(false);
    }
  }

  async function bindProviderToCapability(capability: string, providerId: string, enabled: boolean) {
    setSaving(true);
    setError('');
    setStatus('');
    try {
      const currentRoute = routes.find((item) => item.capability === capability);
      await settingsApi.upsertHouseholdAiRoute(
        householdId,
        capability,
        buildRoutePayload(householdId, capability, currentRoute, providerId || null, enabled),
      );
      setStatus(`${getCapabilityLabel(capability)} route updated`);
      await reload();
    } catch (routeError) {
      setError(routeError instanceof Error ? routeError.message : '鏇存柊鑳藉姏璺敱澶辫触');
    } finally {
      setSaving(false);
    }
  }

  const providerCards = providers.filter(
    (item) => !compact || visibleCapabilities.some((capability) => item.supported_capabilities.includes(capability)),
  );

  return (
    <div className="ai-provider-center">
      <div className="ai-provider-center__toolbar">
        <button className="btn btn--primary" type="button" onClick={startCreate}>Add Provider</button>
        {selectedProvider ? <button className="btn btn--outline" type="button" onClick={() => startEdit(selectedProvider)}>Edit Current Provider</button> : null}
        {selectedProvider && !compact ? (
          <button className="btn btn--outline" type="button" onClick={() => void handleDelete()} disabled={saving}>
            鍒犻櫎褰撳墠鎻愪緵鍟?          </button>
        ) : null}
      </div>
      {loading ? <div className="settings-loading-copy">正在读取提供商配置...</div> : null}
      {error ? <Card><p className="form-error">{error}</p></Card> : null}
      {!loading ? (
        <>
          <div className="ai-config-list">
            {providerCards.length === 0 ? (
              <Card className="ai-config-card">
                <p className="ai-config-muted">No AI provider is available for this household yet. Create one first.</p>
              </Card>
            ) : providerCards.map((provider) => (
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
                      <span className={`ai-pill ${provider.enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>
                        {provider.enabled ? '???' : '???'}
                      </span>
                    </div>
                    <p className="ai-config-card__meta">{provider.provider_code}</p>
                    <p className="ai-config-card__summary">{getProviderModelName(provider) ?? '鏈～鍐欐ā鍨嬪悕'}</p>
                  </div>
                </div>
                <div className="ai-config-chip-list">
                  {provider.supported_capabilities.map((capability) => (
                    <span key={capability} className="ai-pill">{getCapabilityLabel(capability)}</span>
                  ))}
                </div>
              </button>
            ))}
          </div>

          <Card className="ai-config-detail-card">
            <div className="setup-step-panel__header">
              <div>
                <h3>{editingProviderId ? '???????' : '???????'}</h3>
                <p>Use the adapter schema here so provider differences stay out of page code.</p>
              </div>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label htmlFor={`provider-adapter-${householdId}`}>Provider Type</label>
                <select
                  id={`provider-adapter-${householdId}`}
                  className="form-select"
                  value={form.adapterCode}
                  onChange={(event) => setForm(buildProviderFormState(adapters.find((item) => item.adapter_code === event.target.value) ?? null))}
                  disabled={Boolean(editingProviderId)}
                >
                  <option value="">璇烽€夋嫨</option>
                  {adapters.map((adapter) => (
                    <option key={adapter.adapter_code} value={adapter.adapter_code}>{adapter.display_name}</option>
                  ))}
                </select>
              </div>
              {currentAdapter ? (
                <>
                  <p className="ai-config-muted">{currentAdapter.description}</p>
                  <div className="setup-form-grid">
                    {currentAdapter.field_schema.map((field) => (
                      <div key={field.key} className="form-group">
                        <label htmlFor={`${householdId}-${field.key}`}>{field.label}</label>
                        {field.field_type === 'select' ? (
                          <select
                            id={`${householdId}-${field.key}`}
                            className="form-select"
                            value={readFieldValue(form, field.key)}
                            onChange={(event) => setForm((current) => assignFieldValue(current, field.key, event.target.value))}
                          >
                            <option value="">璇烽€夋嫨</option>
                            {field.options.map((option) => (
                              <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                          </select>
                        ) : (
                          <input
                            id={`${householdId}-${field.key}`}
                            className="form-input"
                            type={field.field_type === 'number' ? 'number' : 'text'}
                            value={readFieldValue(form, field.key)}
                            onChange={(event) => setForm((current) => assignFieldValue(current, field.key, event.target.value))}
                            placeholder={field.placeholder ?? undefined}
                            disabled={Boolean(editingProviderId && field.key === 'provider_code')}
                          />
                        )}
                        {field.help_text ? <p className="ai-config-muted">{field.help_text}</p> : null}
                      </div>
                    ))}
                    <div className="form-group">
                      <label>鏀寔鑳藉姏</label>
                      <div className="setup-choice-group">
                        {AI_CAPABILITY_OPTIONS.map((item) => (
                          <label key={item.value} className="setup-choice">
                            <input
                              type="checkbox"
                              checked={form.supportedCapabilities.includes(item.value)}
                              onChange={() => {
                                setForm((current) => ({
                                  ...current,
                                  supportedCapabilities: current.supportedCapabilities.includes(item.value)
                                    ? current.supportedCapabilities.filter((capability) => capability !== item.value)
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
                          onChange={(event) => setForm((current) => ({ ...current, enabled: event.target.checked }))}
                        />
                        <span>Enable immediately after saving</span>
                      </label>
                    </div>
                  </div>
                </>
              ) : null}
              {status ? <div className="setup-form-status">{status}</div> : null}
              <div className="setup-form-actions">
                <button
                  className="btn btn--primary"
                  type="submit"
                  disabled={
                    saving
                    || !currentAdapter
                    || !form.displayName.trim()
                    || !form.providerCode.trim()
                    || !form.modelName.trim()
                    || form.supportedCapabilities.length === 0
                  }
                >
                  {saving ? '???...' : editingProviderId ? '?????' : '?????'}
                </button>
              </div>
            </form>
          </Card>

          <Card className="ai-config-detail-card">
            <div className="setup-step-panel__header">
              <div>
                <h3>{compact ? '鍚戝鎵€闇€鑳藉姏璺敱' : '鑳藉姏璺敱缁戝畾'}</h3>
                <p>{compact ? '????????????????' : '??????????????????????????'}</p>
              </div>
            </div>
            <div className="ai-route-grid">
              {visibleCapabilities.map((capability) => {
                const route = routes.find((item) => item.capability === capability);
                const candidates = providers.filter((item) => item.enabled && item.supported_capabilities.includes(capability));
                return (
                  <div key={capability} className="ai-route-card">
                    <div className="ai-route-card__top">
                      <strong>{getCapabilityLabel(capability)}</strong>
                      <span className={`ai-pill ${route?.enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>
                        {route?.enabled ? '???' : '???'}
                      </span>
                    </div>
                    <div className="form-group">
                      <label htmlFor={`${householdId}-route-${capability}`}>涓绘彁渚涘晢</label>
                      <select
                        id={`${householdId}-route-${capability}`}
                        className="form-select"
                        value={route?.primary_provider_profile_id ?? ''}
                        onChange={(event) => void bindProviderToCapability(capability, event.target.value, Boolean(event.target.value))}
                      >
                        <option value="">Unbound</option>
                        {candidates.map((provider) => (
                          <option key={provider.id} value={provider.id}>{provider.display_name}</option>
                        ))}
                      </select>
                    </div>
                    <button
                      type="button"
                      className="btn btn--outline"
                      onClick={() => void bindProviderToCapability(capability, route?.primary_provider_profile_id ?? '', !route?.enabled)}
                      disabled={!route?.primary_provider_profile_id}
                    >
                      {route?.enabled ? '鍋滅敤璺敱' : '鍚敤璺敱'}
                    </button>
                  </div>
                );
              })}
            </div>
          </Card>
        </>
      ) : null}
    </div>
  );
}

function readFieldValue(form: ProviderFormState, fieldKey: string) {
  return readProviderFormValue(form, fieldKey);
}

function assignFieldValue(form: ProviderFormState, fieldKey: string, value: string): ProviderFormState {
  return assignProviderFormValue(form, fieldKey, value);
}
