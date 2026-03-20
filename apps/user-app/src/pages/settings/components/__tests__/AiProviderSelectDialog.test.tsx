import test from 'node:test';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import type { AiProviderAdapter } from '../../settingsTypes';
import { AiProviderSelectDialog } from '../AiProviderSelectDialog';

function createAdapter(overrides: Partial<AiProviderAdapter> = {}): AiProviderAdapter {
  return {
    plugin_id: 'plugin-openai',
    plugin_name: 'OpenAI',
    adapter_code: 'openai',
    display_name: 'ChatGPT',
    description: '适合直接接入 OpenAI 官方接口。',
    branding: {
      logo_url: null,
      logo_dark_url: null,
      description_locales: {},
    },
    transport_type: 'openai_compatible',
    api_family: 'openai_chat_completions',
    default_privacy_level: 'public_cloud',
    default_supported_capabilities: ['text', 'vision'],
    supported_model_types: ['llm', 'vision'],
    llm_workflow: 'chat',
    supports_model_discovery: false,
    field_schema: [],
    config_ui: {
      field_order: [],
      hidden_fields: [],
      sections: [],
      field_ui: {},
      actions: [],
    },
    model_discovery: {
      enabled: false,
      action_key: null,
      depends_on_fields: [],
      target_field: null,
      debounce_ms: 500,
      empty_state_text: null,
      discovery_hint_text: null,
      discovering_text: null,
      discovered_text_template: null,
    },
    ...overrides,
  };
}

test('供应商选择弹框打开时会带上内容区居中修饰类', () => {
  const markup = renderToStaticMarkup(
    <AiProviderSelectDialog
      open
      locale="zh-CN"
      adapters={[createAdapter()]}
      copy={{
        title: '选择供应商插件',
        description: '先选择供应商，再填写动态表单。',
        close: '关闭',
      }}
      onSelect={() => {}}
      onClose={() => {}}
    />,
  );

  assert.match(markup, /member-modal-overlay ai-provider-select-modal-overlay/);
  assert.match(markup, /ai-provider-select-modal/);
});

test('供应商选择弹框关闭时不渲染任何内容', () => {
  const markup = renderToStaticMarkup(
    <AiProviderSelectDialog
      open={false}
      locale="zh-CN"
      adapters={[createAdapter()]}
      copy={{
        title: '选择供应商插件',
        description: '先选择供应商，再填写动态表单。',
        close: '关闭',
      }}
      onSelect={() => {}}
      onClose={() => {}}
    />,
  );

  assert.equal(markup, '');
});
