import { useEffect, useRef, useState } from 'react';
import {
  assignProviderFormValue,
  buildProviderFormState,
  buildProviderModelDiscoveryPayload,
  readProviderFormValue,
} from '../../setup/setupAiConfig';

type ProviderFormState = ReturnType<typeof buildProviderFormState>;

type AdapterLike = {
  adapter_code: string;
  supports_model_discovery?: boolean;
  model_discovery?: {
    enabled: boolean;
    depends_on_fields: string[];
    target_field: string | null;
    debounce_ms: number;
  };
};

type DiscoveryResult = {
  models: Array<{
    id: string;
    label: string;
  }>;
};

export function useAiProviderModelDiscovery(props: {
  householdId: string;
  adapter: AdapterLike | null;
  form: ProviderFormState;
  onFormChange: (form: ProviderFormState) => void;
  discoverModels: (householdId: string, adapterCode: string, payload: { values: Record<string, unknown> }) => Promise<DiscoveryResult>;
}) {
  const { householdId, adapter, form, onFormChange, discoverModels } = props;
  const [models, setModels] = useState<Array<{ id: string; label: string }>>([]);
  const [discovering, setDiscovering] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const formRef = useRef(form);
  const requestSeqRef = useRef(0);
  const discoveryConfig = adapter?.model_discovery;
  const supportsModelDiscovery = Boolean(adapter?.supports_model_discovery && discoveryConfig?.enabled);
  const dependencyKeys = discoveryConfig?.depends_on_fields ?? [];
  const targetField = discoveryConfig?.target_field ?? null;

  formRef.current = form;

  useEffect(() => {
    setModels([]);
    setStatus('');
    setError('');
  }, [adapter?.adapter_code]);

  async function runDiscovery() {
    if (!adapter || !supportsModelDiscovery) {
      return;
    }
    const payload = buildProviderModelDiscoveryPayload(formRef.current, adapter as never);
    const dependenciesReady = dependencyKeys.every(fieldKey => readProviderFormValue(formRef.current, fieldKey).trim());
    if (!dependenciesReady) {
      setModels([]);
      setStatus('');
      setError('');
      return;
    }

    const requestSeq = ++requestSeqRef.current;
    setDiscovering(true);
    setError('');
    try {
      const result = await discoverModels(householdId, adapter.adapter_code, payload);
      if (requestSeq !== requestSeqRef.current) {
        return;
      }
      setModels(result.models);
      setStatus(result.models.length > 0 ? `found:${result.models.length}` : 'empty');
      const currentTargetValue = targetField ? readProviderFormValue(formRef.current, targetField).trim() : '';
      if (targetField && !currentTargetValue && result.models[0]?.id) {
        onFormChange(assignProviderFormValue(formRef.current, targetField, result.models[0].id));
      }
    } catch (discoveryError) {
      if (requestSeq !== requestSeqRef.current) {
        return;
      }
      setModels([]);
      setStatus('');
      setError(discoveryError instanceof Error ? discoveryError.message : String(discoveryError || '模型列表刷新失败'));
    } finally {
      if (requestSeq === requestSeqRef.current) {
        setDiscovering(false);
      }
    }
  }

  useEffect(() => {
    if (!adapter || !supportsModelDiscovery) {
      return;
    }
    const dependenciesReady = dependencyKeys.every(fieldKey => readProviderFormValue(form, fieldKey).trim());
    if (!dependenciesReady) {
      setModels([]);
      setStatus('');
      setError('');
      return;
    }
    const timer = globalThis.setTimeout(() => {
      void runDiscovery();
    }, discoveryConfig?.debounce_ms ?? 500);
    return () => globalThis.clearTimeout(timer);
  }, [
    adapter,
    householdId,
    supportsModelDiscovery,
    discoveryConfig?.debounce_ms,
    dependencyKeys.map(fieldKey => readProviderFormValue(form, fieldKey)).join('\n'),
  ]);

  return {
    models,
    discovering,
    status,
    error,
    supportsModelDiscovery,
    refreshModels: () => void runDiscovery(),
  };
}
