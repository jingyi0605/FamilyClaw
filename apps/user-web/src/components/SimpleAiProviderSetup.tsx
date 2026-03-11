import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Card } from './base';
import { api } from '../lib/api';
import {
  AI_CAPABILITY_OPTIONS,
  buildCreateProviderPayload,
  buildProviderFormState,
  buildRoutePayload,
} from '../lib/aiConfig';
import type { AiProviderAdapter, AiProviderProfile } from '../lib/types';

type Props = {
  householdId: string;
  onCompleted?: () => void;
};

type ProviderFormState = ReturnType<typeof buildProviderFormState>;

const HIDDEN_SETUP_FIELDS = new Set(['provider_code', 'latency_budget_ms']);

export function SimpleAiProviderSetup({ householdId, onCompleted }: Props) {
  const [adapters, setAdapters] = useState<AiProviderAdapter[]>([]);
  const [form, setForm] = useState<ProviderFormState>(buildProviderFormState());
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
        const adapterRows = await api.listAiProviderAdapters();
        if (cancelled) return;
        setAdapters(adapterRows);
        setForm(current => current.adapterCode ? current : buildProviderFormState(adapterRows[0] ?? null));
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
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentAdapter) {
      setError('请先选择供应商类型');
      return;
    }
    setSaving(true);
    setError('');
    setStatus('正在创建供应商...');
    try {
      // 1. Create provider
      const created = await api.createHouseholdAiProvider(
        householdId, 
        buildCreateProviderPayload(form, currentAdapter)
      );
      
      setStatus('正在配置全场景路由...');
      // 2. Automatically bind all capabilities to this provider
      const allCapabilities = AI_CAPABILITY_OPTIONS.map(item => item.value);
      
      // Need to fetch current routes to build payload correctly
      const routes = await api.listHouseholdAiRoutes(householdId);
      
      await Promise.all(
        allCapabilities.map(capability => {
          const currentRoute = routes.find(item => item.capability === capability);
          return api.upsertHouseholdAiRoute(
            householdId,
            capability,
            buildRoutePayload(householdId, capability, currentRoute, created.id, true)
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
    if (fieldKey === 'display_name') return form.displayName;
    if (fieldKey === 'provider_code') return form.providerCode;
    if (fieldKey === 'base_url') return form.baseUrl;
    if (fieldKey === 'secret_ref') return form.secretRef;
    if (fieldKey === 'model_name') return form.modelName;
    if (fieldKey === 'privacy_level') return form.privacyLevel;
    if (fieldKey === 'latency_budget_ms') return form.latencyBudgetMs;
    return '';
  }

  function assignFieldValue(fieldKey: string, value: string): ProviderFormState {
    if (fieldKey === 'display_name') return { ...form, displayName: value };
    if (fieldKey === 'provider_code') return { ...form, providerCode: value };
    if (fieldKey === 'base_url') return { ...form, baseUrl: value };
    if (fieldKey === 'secret_ref') return { ...form, secretRef: value };
    if (fieldKey === 'model_name') return { ...form, modelName: value };
    if (fieldKey === 'privacy_level') return { ...form, privacyLevel: value };
    if (fieldKey === 'latency_budget_ms') return { ...form, latencyBudgetMs: value };
    return form;
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
              <span>创建后，系统会自动将该供应商设置为所有场景的默认模型（包括文本、问答、多模态等）。如需更详细的路由设置，可在初始化完成后进入配置中心调整。</span>
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
            {saving ? '正在绑定…' : '创建并应用到全场景'}
          </button>
        </div>
      </form>
    </Card>
  );
}
