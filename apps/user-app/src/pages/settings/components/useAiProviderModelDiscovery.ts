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

  formRef.current = form;

  useEffect(() => {
    setModels([]);
    setStatus('');
    setError('');
  }, [adapter?.adapter_code]);

  async function runDiscovery() {
    if (!adapter?.supports_model_discovery) {
      return;
    }
    const payload = buildProviderModelDiscoveryPayload(formRef.current, adapter as never);
    const baseUrl = String(payload.values.base_url ?? '').trim();
    if (!baseUrl) {
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
      const currentModelName = readProviderFormValue(formRef.current, 'model_name').trim();
      if (!currentModelName && result.models[0]?.id) {
        onFormChange(assignProviderFormValue(formRef.current, 'model_name', result.models[0].id));
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
    if (!adapter?.supports_model_discovery) {
      return;
    }
    const payload = buildProviderModelDiscoveryPayload(form, adapter as never);
    const baseUrl = String(payload.values.base_url ?? '').trim();
    if (!baseUrl) {
      setModels([]);
      setStatus('');
      setError('');
      return;
    }
    const timer = globalThis.setTimeout(() => {
      void runDiscovery();
    }, 500);
    return () => globalThis.clearTimeout(timer);
  }, [adapter, form.baseUrl, form.secretRef, form.dynamicFields, householdId]);

  return {
    models,
    discovering,
    status,
    error,
    supportsModelDiscovery: Boolean(adapter?.supports_model_discovery),
    refreshModels: () => void runDiscovery(),
  };
}
