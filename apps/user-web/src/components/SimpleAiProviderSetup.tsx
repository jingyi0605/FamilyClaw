import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Card } from './base';
import { api } from '../lib/api';
import {
  assignProviderFormValue,
  buildCreateProviderPayload,
  buildProviderFormState,
  buildRoutePayload,
  buildUpdateProviderPayload,
  getProviderAdapterCode,
  readProviderFormValue,
  SETUP_ROUTE_CAPABILITIES,
  toProviderFormState,
} from '../lib/aiConfig';
import type { AiCapabilityRoute, AiProviderAdapter, AiProviderProfile } from '../lib/types';

type Props = {
  householdId: string;
  onCompleted?: () => void;
};

type ProviderFormState = ReturnType<typeof buildProviderFormState>;

const HIDDEN_SETUP_FIELDS = new Set(['provider_code', 'latency_budget_ms']);

export function SimpleAiProviderSetup({ householdId, onCompleted }: Props) {
  const [adapters, setAdapters] = useState<AiProviderAdapter[]>([]);
  const [form, setForm] = useState<ProviderFormState>(buildProviderFormState());
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const currentAdapter = useMemo(
    () => adapters.find(item => item.adapter_code === form.adapterCode) ?? null,
    [adapters, form.adapterCode],
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
        if (cancelled) return;

        const existingProvider = pickSetupProvider(providerRows, routeRows);
        const existingAdapter = existingProvider
          ? adapterRows.find(item => item.adapter_code === getProviderAdapterCode(existingProvider)) ?? adapterRows[0] ?? null
          : null;

        setAdapters(adapterRows);
        setEditingProviderId(existingProvider?.id ?? null);
        setForm(
          existingProvider
            ? toProviderFormState(existingProvider, existingAdapter)
            : buildProviderFormState(adapterRows[0] ?? null),
        );
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
    return () => { cancelled = true; };
  }, [householdId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentAdapter) {
      setError('请先选择供应商类型');
      return;
    }
    setSaving(true);
    setError('');
    setStatus(editingProviderId ? '正在保存供应商...' : '正在创建供应商...');
    try {
      const providerId = editingProviderId
        ? editingProviderId
        : (
          await api.createHouseholdAiProvider(
            householdId,
            buildCreateProviderPayload(form, currentAdapter),
          )
        ).id;

      if (editingProviderId) {
        await api.updateHouseholdAiProvider(
          householdId,
          editingProviderId,
          buildUpdateProviderPayload(form, currentAdapter),
        );
      } else {
        setEditingProviderId(providerId);
      }
      
      setStatus('正在配置默认能力路由...');
      const supportedCapabilities = form.supportedCapabilities;

      if (supportedCapabilities.length === 0) {
        throw new Error('当前供应商没有可绑定的能力');
      }
      
      const routes = await api.listHouseholdAiRoutes(householdId);
      
      await Promise.all(
        supportedCapabilities.map(capability => {
          const currentRoute = routes.find(item => item.capability === capability);
          return api.upsertHouseholdAiRoute(
            householdId,
            capability,
            buildRoutePayload(householdId, capability, currentRoute, providerId, true)
          );
        })
      );
      
      setStatus('AI 供应商配置完成！');
      onCompleted?.();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存供应商配置失败');
    } finally {
      setSaving(false);
    }
  }

  function readFieldValue(fieldKey: string) {
    return readProviderFormValue(form, fieldKey);
  }

  function assignFieldValue(fieldKey: string, value: string): ProviderFormState {
    return assignProviderFormValue(form, fieldKey, value);
  }

  if (loading) {
    return <Card><p>正在加载...</p></Card>;
  }

  return (
    <Card className="ai-config-detail-card">
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor={`provider-adapter-${householdId}`}>选择供应商平台</label>
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
              {currentAdapter.field_schema.filter(field => !HIDDEN_SETUP_FIELDS.has(field.key)).map(field => (
                <div key={field.key} className="form-group">
                  <label htmlFor={`${householdId}-${field.key}`}>{field.label}</label>
                  {field.field_type === 'select' ? (
                    <select
                      id={`${householdId}-${field.key}`}
                      className="form-select"
                      value={readFieldValue(field.key)}
                      onChange={event => setForm(assignFieldValue(field.key, event.target.value))}
                    >
                      <option value="">请选择</option>
                      {field.options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  ) : (
                    <input
                      id={`${householdId}-${field.key}`}
                      className="form-input"
                      type={field.field_type === 'number' ? 'number' : 'text'}
                      value={readFieldValue(field.key)}
                      onChange={event => setForm(assignFieldValue(field.key, event.target.value))}
                      placeholder={field.placeholder ?? undefined}
                    />
                  )}
                  {field.help_text && <p className="ai-config-muted">{field.help_text}</p>}
                </div>
              ))}
            </div>
            <div className="setup-inline-tip">
              <strong>提示：</strong>
              <span>创建后，系统只会把这个供应商绑定到它明确支持的能力。别拿纯文本模型去硬绑语音、视觉、重排，那本来就该失败。</span>
            </div>
          </>
        )}
        
        {error && <div className="form-error">{error}</div>}
        {status && <div className="setup-form-status">{status}</div>}
        
        <div className="setup-form-actions">
          <button
            className="btn btn--primary"
            type="submit"
            disabled={saving || !currentAdapter || !form.displayName.trim() || !form.modelName.trim()}
          >
            {saving ? '正在绑定…' : editingProviderId ? '保存并更新全场景' : '创建并应用到全场景'}
          </button>
        </div>
      </form>
    </Card>
  );
}

function pickSetupProvider(providers: AiProviderProfile[], routes: AiCapabilityRoute[]) {
  const routeProviderIds = SETUP_ROUTE_CAPABILITIES
    .map(capability => routes.find(item => item.capability === capability)?.primary_provider_profile_id)
    .filter((providerId): providerId is string => Boolean(providerId));

  for (const providerId of routeProviderIds) {
    const matchedProvider = providers.find(item => item.id === providerId);
    if (matchedProvider) {
      return matchedProvider;
    }
  }

  return providers[0] ?? null;
}
