import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useI18n } from '../../../runtime';
import { Card } from '../../family/base';
import {
  AI_CAPABILITY_OPTIONS,
  assignProviderFormValue,
  buildCreateProviderPayload,
  buildProviderFormState,
  buildRoutePayload,
  buildUpdateProviderPayload,
  getProviderAdapterCode,
  getProviderModelName,
  readProviderFormValue,
  toProviderFormState,
} from '../../setup/setupAiConfig';
import { settingsApi } from '../settingsApi';
import type { AiCapabilityRoute, AiProviderAdapter, AiProviderField, AiProviderFieldOption, AiProviderProfile } from '../settingsTypes';

type ProviderFormState = ReturnType<typeof buildProviderFormState>;

function pickLocaleText(
  locale: string | undefined,
  values: { zhCN: string; zhTW: string; enUS: string },
) {
  if (locale?.toLowerCase().startsWith('en')) return values.enUS;
  if (locale?.toLowerCase().startsWith('zh-tw')) return values.zhTW;
  return values.zhCN;
}

function getLocalizedCapabilityLabel(capability: string, locale: string | undefined) {
  switch (capability) {
    case 'qa_generation':
      return pickLocaleText(locale, { zhCN: '家庭问答生成', zhTW: '家庭問答生成', enUS: 'Household Q&A generation' });
    case 'qa_structured_answer':
      return pickLocaleText(locale, { zhCN: '结构化问答', zhTW: '結構化問答', enUS: 'Structured Q&A' });
    case 'reminder_copywriting':
      return pickLocaleText(locale, { zhCN: '提醒文案', zhTW: '提醒文案', enUS: 'Reminder copywriting' });
    case 'scene_explanation':
      return pickLocaleText(locale, { zhCN: '场景解释', zhTW: '場景解釋', enUS: 'Scene explanation' });
    case 'embedding':
      return pickLocaleText(locale, { zhCN: '向量检索', zhTW: '向量檢索', enUS: 'Embedding search' });
    case 'rerank':
      return pickLocaleText(locale, { zhCN: '结果重排', zhTW: '結果重排', enUS: 'Reranking' });
    case 'stt':
      return pickLocaleText(locale, { zhCN: '语音转文字', zhTW: '語音轉文字', enUS: 'Speech to text' });
    case 'tts':
      return pickLocaleText(locale, { zhCN: '文字转语音', zhTW: '文字轉語音', enUS: 'Text to speech' });
    case 'vision':
      return pickLocaleText(locale, { zhCN: '视觉理解', zhTW: '視覺理解', enUS: 'Vision understanding' });
    default:
      return capability;
  }
}

function getLocalizedAdapterMeta(adapterCode: string, locale: string | undefined) {
  switch (adapterCode) {
    case 'chatgpt':
      return {
        label: 'ChatGPT',
        description: pickLocaleText(locale, {
          zhCN: '适合直接接入 OpenAI 官方接口或兼容 OpenAI Chat Completions 的网关。',
          zhTW: '適合直接接入 OpenAI 官方介面或相容 OpenAI Chat Completions 的閘道。',
          enUS: 'Best for the official OpenAI API or gateways compatible with OpenAI Chat Completions.',
        }),
      };
    case 'deepseek':
      return {
        label: 'DeepSeek',
        description: pickLocaleText(locale, {
          zhCN: 'DeepSeek 官方兼容接口，适合通用问答，也能处理轻量代码解释。',
          zhTW: 'DeepSeek 官方相容介面，適合通用問答，也能處理輕量程式碼解釋。',
          enUS: 'DeepSeek official compatible endpoint for general Q&A and light code explanation.',
        }),
      };
    case 'qwen':
      return {
        label: 'Qwen',
        description: pickLocaleText(locale, {
          zhCN: '阿里云百炼兼容接口，国内环境接入通常更直接。',
          zhTW: '阿里雲百煉相容介面，在中國大陸環境通常更容易接入。',
          enUS: 'Alibaba DashScope compatible endpoint, often easier to access from mainland China.',
        }),
      };
    case 'glm':
      return {
        label: 'GLM',
        description: pickLocaleText(locale, {
          zhCN: '智谱 GLM 的兼容配置模板，继续走统一网关模型。',
          zhTW: '智譜 GLM 的相容設定範本，仍然走統一閘道模型。',
          enUS: 'Compatible GLM template that still uses the shared gateway model flow.',
        }),
      };
    case 'siliconflow':
      return {
        label: 'SiliconFlow',
        description: pickLocaleText(locale, {
          zhCN: '适合托管多家模型，也方便切换不同推理模型。',
          zhTW: '適合託管多家模型，也方便切換不同推理模型。',
          enUS: 'Useful for hosting multiple model families and switching inference models easily.',
        }),
      };
    case 'kimi':
      return {
        label: 'Kimi',
        description: pickLocaleText(locale, {
          zhCN: 'Moonshot 官方兼容接口，适合长上下文问答。',
          zhTW: 'Moonshot 官方相容介面，適合長上下文問答。',
          enUS: 'Moonshot official compatible endpoint, suitable for long-context conversations.',
        }),
      };
    case 'minimax':
      return {
        label: 'MiniMax',
        description: pickLocaleText(locale, {
          zhCN: '保留最小接入字段，不把一堆高级参数直接丢给普通用户。',
          zhTW: '保留最小接入欄位，不把一堆進階參數直接丟給一般使用者。',
          enUS: 'Keeps the required fields minimal instead of exposing too many advanced parameters.',
        }),
      };
    case 'claude':
      return {
        label: 'Claude',
        description: pickLocaleText(locale, {
          zhCN: 'Anthropic 官方 Messages API，使用原生协议，不走 OpenAI 兼容层。',
          zhTW: 'Anthropic 官方 Messages API，使用原生協定，不走 OpenAI 相容層。',
          enUS: 'Anthropic official Messages API using the native protocol instead of the OpenAI-compatible layer.',
        }),
      };
    case 'gemini':
      return {
        label: 'Gemini',
        description: pickLocaleText(locale, {
          zhCN: 'Google Gemini 官方 GenerateContent API，同样使用原生协议。',
          zhTW: 'Google Gemini 官方 GenerateContent API，同樣使用原生協定。',
          enUS: 'Google Gemini official GenerateContent API using the native protocol.',
        }),
      };
    case 'openrouter':
      return {
        label: 'OpenRouter',
        description: pickLocaleText(locale, {
          zhCN: '聚合多家模型的平台，保留少量 provider 专用字段，由运行时统一补请求头。',
          zhTW: '聚合多家模型的平台，保留少量 provider 專用欄位，由執行階段統一補請求標頭。',
          enUS: 'Aggregator for multiple providers with only a few provider-specific fields exposed here.',
        }),
      };
    case 'doubao':
      return {
        label: 'Doubao Ark',
        description: pickLocaleText(locale, {
          zhCN: '火山引擎 Ark 官方兼容接口，适合国内主模型接入。',
          zhTW: '火山引擎 Ark 官方相容介面，適合中國大陸主模型接入。',
          enUS: 'Volcengine Ark official compatible endpoint for primary models in mainland China.',
        }),
      };
    case 'doubao-coding':
      return {
        label: 'Doubao Coding',
        description: pickLocaleText(locale, {
          zhCN: '把代码和计划型模型单独分出来，避免和普通问答模型混在一起。',
          zhTW: '把程式碼與規劃型模型單獨分出來，避免和一般問答模型混在一起。',
          enUS: 'Separate coding and planning models from general Q&A models.',
        }),
      };
    case 'byteplus':
      return {
        label: 'BytePlus ModelArk',
        description: pickLocaleText(locale, {
          zhCN: 'BytePlus 国际版兼容接口，适合海外环境统一接入。',
          zhTW: 'BytePlus 國際版相容介面，適合海外環境統一接入。',
          enUS: 'BytePlus international compatible endpoint for overseas environments.',
        }),
      };
    case 'byteplus-coding':
      return {
        label: 'BytePlus Coding',
        description: pickLocaleText(locale, {
          zhCN: '给代码解释、生成和计划类能力预留独立模型入口。',
          zhTW: '替程式碼解釋、生成與規劃能力保留獨立模型入口。',
          enUS: 'Dedicated model entry for coding, generation, and planning capabilities.',
        }),
      };
    default:
      return null;
  }
}

function localizeExamplePrefix(text: string | null | undefined, locale: string | undefined) {
  if (!text) return text ?? null;
  if (!text.startsWith('例如：')) return text;
  return `${pickLocaleText(locale, { zhCN: '例如：', zhTW: '例如：', enUS: 'For example: ' })}${text.slice(3)}`;
}

function getLocalizedField(field: AiProviderField, locale: string | undefined) {
  const label = (() => {
    switch (field.key) {
      case 'display_name':
        return pickLocaleText(locale, { zhCN: '显示名称', zhTW: '顯示名稱', enUS: 'Display name' });
      case 'provider_code':
        return pickLocaleText(locale, { zhCN: '供应商编码', zhTW: '供應商代碼', enUS: 'Provider code' });
      case 'base_url':
        return 'Base URL';
      case 'secret_ref':
        return pickLocaleText(locale, { zhCN: '密钥引用', zhTW: '密鑰引用', enUS: 'Secret reference' });
      case 'model_name':
        return pickLocaleText(locale, { zhCN: '模型名', zhTW: '模型名稱', enUS: 'Model name' });
      case 'privacy_level':
        return pickLocaleText(locale, { zhCN: '隐私等级', zhTW: '隱私等級', enUS: 'Privacy level' });
      case 'anthropic_version':
        return pickLocaleText(locale, { zhCN: 'Anthropic 版本', zhTW: 'Anthropic 版本', enUS: 'Anthropic version' });
      case 'site_url':
        return pickLocaleText(locale, { zhCN: '站点地址', zhTW: '站點位址', enUS: 'Site URL' });
      case 'app_name':
        return pickLocaleText(locale, { zhCN: '应用名称', zhTW: '應用名稱', enUS: 'App name' });
      case 'latency_budget_ms':
        return pickLocaleText(locale, { zhCN: '延迟预算（毫秒）', zhTW: '延遲預算（毫秒）', enUS: 'Latency budget (ms)' });
      default:
        return field.label;
    }
  })();
  const helpText = (() => {
    switch (field.key) {
      case 'base_url':
        return pickLocaleText(locale, {
          zhCN: '默认填官方地址；如果你走企业网关或代理，再自己改。',
          zhTW: '預設填入官方位址；如果您使用企業閘道或代理，再自行修改。',
          enUS: 'Defaults to the official endpoint. Change it only if you use a company gateway or proxy.',
        });
      case 'site_url':
        return pickLocaleText(locale, {
          zhCN: '如果填写，运行时会作为 HTTP-Referer 发给 OpenRouter。',
          zhTW: '如果填寫，執行時會作為 HTTP-Referer 傳給 OpenRouter。',
          enUS: 'If provided, it will be sent to OpenRouter as the HTTP-Referer header.',
        });
      case 'app_name':
        return pickLocaleText(locale, {
          zhCN: '如果填写，运行时会作为 X-Title 发给 OpenRouter。',
          zhTW: '如果填寫，執行時會作為 X-Title 傳給 OpenRouter。',
          enUS: 'If provided, it will be sent to OpenRouter as the X-Title header.',
        });
      default:
        return field.help_text;
    }
  })();
  const options: AiProviderFieldOption[] = field.options.map(option => ({
    ...option,
    label: field.key === 'privacy_level'
      ? ({
        public_cloud: pickLocaleText(locale, { zhCN: '公有云', zhTW: '公有雲', enUS: 'Public cloud' }),
        private_cloud: pickLocaleText(locale, { zhCN: '私有云', zhTW: '私有雲', enUS: 'Private cloud' }),
        local_only: pickLocaleText(locale, { zhCN: '仅本地', zhTW: '僅本地', enUS: 'Local only' }),
      } as Record<string, string>)[option.value] ?? option.label
      : localizeExamplePrefix(option.label, locale) ?? option.label,
  }));

  return {
    ...field,
    label,
    placeholder: localizeExamplePrefix(field.placeholder, locale),
    help_text: localizeExamplePrefix(helpText, locale),
    options,
  };
}

export function AiProviderConfigPanel(props: {
  householdId: string;
  compact?: boolean;
  capabilityFilter?: string[];
  onChanged?: () => Promise<void> | void;
}) {
  const { locale } = useI18n();
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
    () => capabilityFilter ?? AI_CAPABILITY_OPTIONS.map(item => item.value),
    [capabilityFilter],
  );
  const localizedCapabilityOptions = useMemo(
    () => AI_CAPABILITY_OPTIONS.map(item => ({ ...item, label: getLocalizedCapabilityLabel(item.value, locale) })),
    [locale],
  );
  const currentAdapter = useMemo(
    () => adapters.find(item => item.adapter_code === form.adapterCode) ?? null,
    [adapters, form.adapterCode],
  );
  const selectedProvider = useMemo(
    () => providers.find(item => item.id === selectedProviderId) ?? null,
    [providers, selectedProviderId],
  );
  const copy = {
    loadFailed: pickLocaleText(locale, { zhCN: '加载模型服务失败', zhTW: '載入模型服務失敗', enUS: 'Failed to load model providers' }),
    selectTypeFirst: pickLocaleText(locale, { zhCN: '请先选择服务类型', zhTW: '請先選擇服務類型', enUS: 'Select a provider type first' }),
    updatedStatus: pickLocaleText(locale, { zhCN: '模型服务已更新', zhTW: '模型服務已更新', enUS: 'Model provider updated' }),
    addedStatus: pickLocaleText(locale, { zhCN: '模型服务已添加', zhTW: '模型服務已新增', enUS: 'Model provider added' }),
    saveFailed: pickLocaleText(locale, { zhCN: '保存模型服务失败', zhTW: '儲存模型服務失敗', enUS: 'Failed to save the model provider' }),
    deletedStatus: pickLocaleText(locale, { zhCN: '模型服务已删除', zhTW: '模型服務已刪除', enUS: 'Model provider deleted' }),
    deleteFailed: pickLocaleText(locale, { zhCN: '删除模型服务失败', zhTW: '刪除模型服務失敗', enUS: 'Failed to delete the model provider' }),
    routeUpdated: (capability: string) => pickLocaleText(locale, {
      zhCN: `${getLocalizedCapabilityLabel(capability, locale)} 已更新`,
      zhTW: `${getLocalizedCapabilityLabel(capability, locale)} 已更新`,
      enUS: `${getLocalizedCapabilityLabel(capability, locale)} updated`,
    }),
    routeFailed: pickLocaleText(locale, { zhCN: '更新能力分配失败', zhTW: '更新能力分配失敗', enUS: 'Failed to update the capability assignment' }),
    addProvider: pickLocaleText(locale, { zhCN: '添加模型服务', zhTW: '新增模型服務', enUS: 'Add model provider' }),
    editProvider: pickLocaleText(locale, { zhCN: '编辑当前服务', zhTW: '編輯目前服務', enUS: 'Edit current provider' }),
    deleteProvider: pickLocaleText(locale, { zhCN: '删除当前服务', zhTW: '刪除目前服務', enUS: 'Delete current provider' }),
    loading: pickLocaleText(locale, { zhCN: '正在读取模型服务信息...', zhTW: '正在讀取模型服務資訊...', enUS: 'Loading model providers...' }),
    emptyProviders: pickLocaleText(locale, { zhCN: '还没有可用的模型服务，先添加一个吧。', zhTW: '還沒有可用的模型服務，先新增一個吧。', enUS: 'No model providers yet. Add one first.' }),
    enabled: pickLocaleText(locale, { zhCN: '已启用', zhTW: '已啟用', enUS: 'Enabled' }),
    disabled: pickLocaleText(locale, { zhCN: '已停用', zhTW: '已停用', enUS: 'Disabled' }),
    modelNameEmpty: pickLocaleText(locale, { zhCN: '还没有填写模型名称', zhTW: '還沒有填寫模型名稱', enUS: 'No model name yet' }),
    editTitle: pickLocaleText(locale, { zhCN: '编辑模型服务', zhTW: '編輯模型服務', enUS: 'Edit model provider' }),
    addTitle: pickLocaleText(locale, { zhCN: '添加模型服务', zhTW: '新增模型服務', enUS: 'Add model provider' }),
    formDescription: pickLocaleText(locale, {
      zhCN: '在这里填写服务地址、密钥和模型信息，保存后就可以分配给不同能力使用。',
      zhTW: '在這裡填寫服務位址、密鑰和模型資訊，儲存後就可以分配給不同能力使用。',
      enUS: 'Enter the endpoint, secret, and model details here. After saving, you can assign this provider to different capabilities.',
    }),
    providerTypeLabel: pickLocaleText(locale, { zhCN: '服务类型', zhTW: '服務類型', enUS: 'Provider type' }),
    selectPlaceholder: pickLocaleText(locale, { zhCN: '请选择', zhTW: '請選擇', enUS: 'Select' }),
    capabilityCheckboxLabel: pickLocaleText(locale, { zhCN: '可用于哪些能力', zhTW: '可用於哪些能力', enUS: 'Supported capabilities' }),
    enableAfterSave: pickLocaleText(locale, { zhCN: '保存后立即启用', zhTW: '儲存後立即啟用', enUS: 'Enable immediately after saving' }),
    saving: pickLocaleText(locale, { zhCN: '保存中...', zhTW: '儲存中...', enUS: 'Saving...' }),
    saveProvider: pickLocaleText(locale, { zhCN: '保存服务', zhTW: '儲存服務', enUS: 'Save provider' }),
    submitAddProvider: pickLocaleText(locale, { zhCN: '添加服务', zhTW: '新增服務', enUS: 'Add provider' }),
    compactRouteTitle: pickLocaleText(locale, { zhCN: '当前需要的能力', zhTW: '目前需要的能力', enUS: 'Capabilities needed right now' }),
    routeTitle: pickLocaleText(locale, { zhCN: '能力分配', zhTW: '能力分配', enUS: 'Capability routing' }),
    compactRouteDescription: pickLocaleText(locale, { zhCN: '这里只显示当前流程需要用到的能力。', zhTW: '這裡只顯示目前流程需要用到的能力。', enUS: 'Only the capabilities required by the current flow are shown here.' }),
    routeDescription: pickLocaleText(locale, { zhCN: '为不同能力选择默认使用的模型服务，AI 会按这里的设置来工作。', zhTW: '為不同能力選擇預設使用的模型服務，AI 會依照這裡的設定運作。', enUS: 'Choose the default model provider for each capability. AI will follow these routing settings.' }),
    routeDisabled: pickLocaleText(locale, { zhCN: '未启用', zhTW: '未啟用', enUS: 'Disabled' }),
    routeProviderLabel: pickLocaleText(locale, { zhCN: '默认使用的服务', zhTW: '預設使用的服務', enUS: 'Default provider' }),
    routeEmpty: pickLocaleText(locale, { zhCN: '暂不选择', zhTW: '暫不選擇', enUS: 'Not selected yet' }),
    pauseUse: pickLocaleText(locale, { zhCN: '暂停使用', zhTW: '暫停使用', enUS: 'Pause' }),
    startUse: pickLocaleText(locale, { zhCN: '开始使用', zhTW: '開始使用', enUS: 'Start using' }),
  };

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
        if (cancelled) return;
        setAdapters(adapterRows);
        setProviders(providerRows);
        setRoutes(routeRows);
        setSelectedProviderId(current => (providerRows.some(item => item.id === current) ? current : (providerRows[0]?.id ?? '')));
        if (!editingProviderId) {
          setForm(current => current.adapterCode ? current : buildProviderFormState(adapterRows[0] ?? null));
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : copy.loadFailed);
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
      setError(copy.selectTypeFirst);
      return;
    }
    setSaving(true);
    setError('');
    setStatus('');
    try {
      if (editingProviderId) {
        await settingsApi.updateHouseholdAiProvider(householdId, editingProviderId, buildUpdateProviderPayload(form, currentAdapter));
        setStatus(copy.updatedStatus);
      } else {
        const created = await settingsApi.createHouseholdAiProvider(householdId, buildCreateProviderPayload(form, currentAdapter));
        setEditingProviderId(created.id);
        setSelectedProviderId(created.id);
        setStatus(copy.addedStatus);
      }
      await reload();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveFailed);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selectedProvider) return;
    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.deleteHouseholdAiProvider(householdId, selectedProvider.id);
      setEditingProviderId(null);
      setSelectedProviderId('');
      setForm(buildProviderFormState(adapters[0] ?? null));
      setStatus(copy.deletedStatus);
      await reload();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : copy.deleteFailed);
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
      await settingsApi.upsertHouseholdAiRoute(
        householdId,
        capability,
        buildRoutePayload(householdId, capability, currentRoute, providerId || null, enabled),
      );
      setStatus(copy.routeUpdated(capability));
      await reload();
    } catch (routeError) {
      setError(routeError instanceof Error ? routeError.message : copy.routeFailed);
    } finally {
      setSaving(false);
    }
  }

  const providerCards = providers.filter(
    item => !compact || visibleCapabilities.some(capability => item.supported_capabilities.includes(capability)),
  );

  return (
    <div className="ai-provider-center">
      <div className="ai-provider-center__toolbar">
        <button className="btn btn--primary" type="button" onClick={startCreate}>{copy.addProvider}</button>
        {selectedProvider ? <button className="btn btn--outline" type="button" onClick={() => startEdit(selectedProvider)}>{copy.editProvider}</button> : null}
        {selectedProvider && !compact ? <button className="btn btn--outline" type="button" onClick={() => void handleDelete()} disabled={saving}>{copy.deleteProvider}</button> : null}
      </div>

      {loading ? <div className="settings-loading-copy">{copy.loading}</div> : null}
      {error ? <Card><p className="form-error">{error}</p></Card> : null}

      {!loading ? (
        <>
          <div className="ai-config-list">
            {providerCards.length === 0 ? (
              <Card className="ai-config-card">
                <p className="ai-config-muted">{copy.emptyProviders}</p>
              </Card>
            ) : providerCards.map(provider => {
              const adapterMeta = getLocalizedAdapterMeta(getProviderAdapterCode(provider), locale);
              return (
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
                        {provider.enabled ? copy.enabled : copy.disabled}
                      </span>
                    </div>
                    <p className="ai-config-card__meta">{provider.provider_code}</p>
                    <p className="ai-config-card__summary">{getProviderModelName(provider) ?? copy.modelNameEmpty}</p>
                    {adapterMeta?.label ? <p className="ai-config-muted">{adapterMeta.label}</p> : null}
                  </div>
                </div>
                <div className="ai-config-chip-list">
                  {provider.supported_capabilities.map(capability => (
                    <span key={capability} className="ai-pill">{getLocalizedCapabilityLabel(capability, locale)}</span>
                  ))}
                </div>
              </button>
              );
            })}
          </div>

          <Card className="ai-config-detail-card">
            <div className="setup-step-panel__header">
              <div>
                <h3>{editingProviderId ? copy.editTitle : copy.addTitle}</h3>
                <p>{copy.formDescription}</p>
              </div>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label htmlFor={`provider-adapter-${householdId}`}>{copy.providerTypeLabel}</label>
                <select
                  id={`provider-adapter-${householdId}`}
                  className="form-select"
                  value={form.adapterCode}
                  onChange={event => setForm(buildProviderFormState(adapters.find(item => item.adapter_code === event.target.value) ?? null))}
                  disabled={Boolean(editingProviderId)}
                >
                  <option value="">{copy.selectPlaceholder}</option>
                  {adapters.map(adapter => {
                    const adapterMeta = getLocalizedAdapterMeta(adapter.adapter_code, locale);
                    return <option key={adapter.adapter_code} value={adapter.adapter_code}>{adapterMeta?.label ?? adapter.display_name}</option>;
                  })}
                </select>
              </div>
              {currentAdapter ? (
                <>
                  <p className="ai-config-muted">{getLocalizedAdapterMeta(currentAdapter.adapter_code, locale)?.description ?? currentAdapter.description}</p>
                  <div className="setup-form-grid">
                    {currentAdapter.field_schema.map(field => {
                      const localizedField = getLocalizedField(field, locale);
                      return (
                      <div key={field.key} className="form-group">
                        <label htmlFor={`${householdId}-${field.key}`}>{localizedField.label}</label>
                        {localizedField.field_type === 'select' ? (
                          <select
                            id={`${householdId}-${field.key}`}
                            className="form-select"
                            value={readFieldValue(form, field.key)}
                            onChange={event => setForm(current => assignFieldValue(current, field.key, event.target.value))}
                          >
                            <option value="">{copy.selectPlaceholder}</option>
                            {localizedField.options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                          </select>
                        ) : (
                          <input
                            id={`${householdId}-${field.key}`}
                            className="form-input"
                            type={localizedField.field_type === 'number' ? 'number' : 'text'}
                            value={readFieldValue(form, field.key)}
                            onChange={event => setForm(current => assignFieldValue(current, field.key, event.target.value))}
                            placeholder={localizedField.placeholder ?? undefined}
                            disabled={Boolean(editingProviderId && field.key === 'provider_code')}
                          />
                        )}
                        {localizedField.help_text ? <p className="ai-config-muted">{localizedField.help_text}</p> : null}
                      </div>
                      );
                    })}
                    <div className="form-group">
                      <label>{copy.capabilityCheckboxLabel}</label>
                      <div className="setup-choice-group">
                        {localizedCapabilityOptions.map(item => (
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
                        <input type="checkbox" checked={form.enabled} onChange={event => setForm(current => ({ ...current, enabled: event.target.checked }))} />
                        <span>{copy.enableAfterSave}</span>
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
                  disabled={saving || !currentAdapter || !form.displayName.trim() || !form.providerCode.trim() || !form.modelName.trim() || form.supportedCapabilities.length === 0}
                >
                  {saving ? copy.saving : editingProviderId ? copy.saveProvider : copy.submitAddProvider}
                </button>
              </div>
            </form>
          </Card>

          <Card className="ai-config-detail-card">
            <div className="setup-step-panel__header">
              <div>
                <h3>{compact ? copy.compactRouteTitle : copy.routeTitle}</h3>
                <p>{compact ? copy.compactRouteDescription : copy.routeDescription}</p>
              </div>
            </div>
            <div className="ai-route-grid">
              {visibleCapabilities.map(capability => {
                const route = routes.find(item => item.capability === capability);
                const candidates = providers.filter(item => item.enabled && item.supported_capabilities.includes(capability));
                return (
                  <div key={capability} className="ai-route-card">
                    <div className="ai-route-card__top">
                      <strong>{getLocalizedCapabilityLabel(capability, locale)}</strong>
                      <span className={`ai-pill ${route?.enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>{route?.enabled ? copy.enabled : copy.routeDisabled}</span>
                    </div>
                    <div className="form-group">
                      <label htmlFor={`${householdId}-route-${capability}`}>{copy.routeProviderLabel}</label>
                      <select
                        id={`${householdId}-route-${capability}`}
                        className="form-select"
                        value={route?.primary_provider_profile_id ?? ''}
                        onChange={event => void bindProviderToCapability(capability, event.target.value, Boolean(event.target.value))}
                      >
                        <option value="">{copy.routeEmpty}</option>
                        {candidates.map(provider => <option key={provider.id} value={provider.id}>{provider.display_name}</option>)}
                      </select>
                    </div>
                    <button
                      type="button"
                      className="btn btn--outline"
                      onClick={() => void bindProviderToCapability(capability, route?.primary_provider_profile_id ?? '', !route?.enabled)}
                      disabled={!route?.primary_provider_profile_id}
                    >
                      {route?.enabled ? copy.pauseUse : copy.startUse}
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
