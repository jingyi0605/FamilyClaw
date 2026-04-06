import test from 'node:test';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import type { AiProviderProfile } from '../../settingsTypes';
import { AiProviderDetailDialog } from '../AiProviderDetailDialog';

function createProvider(overrides: Partial<AiProviderProfile> = {}): AiProviderProfile {
  return {
    id: 'provider-1',
    provider_code: 'openai',
    display_name: '家庭主模型',
    plugin_id: 'plugin-openai',
    plugin_enabled: true,
    plugin_disabled_reason: null,
    transport_type: 'openai_compatible',
    api_family: 'openai_chat_completions',
    base_url: 'https://api.example.com/v1',
    api_version: null,
    secret_ref: 'sk-test-secret',
    enabled: true,
    supported_capabilities: ['text'],
    privacy_level: 'public_cloud',
    latency_budget_ms: 1500,
    cost_policy: {},
    extra_config: {
      model_name: 'gpt-4.1',
    },
    updated_at: '2026-04-06T23:00:00Z',
    ...overrides,
  };
}

test('模型详情弹框会在关闭和编辑之间渲染删除按钮', () => {
  const markup = renderToStaticMarkup(
    <AiProviderDetailDialog
      open
      provider={createProvider()}
      adapter={null}
      plugin={null}
      routes={[]}
      locale="zh-CN"
      copy={{
        enabled: '已启用',
        disabled: '已停用',
        pluginDisabled: '插件已停用',
        pluginDisabledTitle: '插件不可用',
        pluginDisabledFallback: '请先恢复插件',
        modelNameEmpty: '未填写模型',
        pluginLabel: '来源插件',
        pluginVersionLabel: '插件版本',
        pluginUpdateStateLabel: '更新状态',
        llmWorkflow: '工作流',
        updatedAtLabel: '最近更新',
        summaryRouteTitle: '能力分配',
        summaryRouteEmpty: '暂无能力',
        summaryConfigTitle: '基础配置',
        close: '关闭',
        delete: '删除当前服务',
        deleting: '删除中...',
        edit: '编辑当前服务',
      }}
      onClose={() => {}}
      onDelete={() => {}}
      onEdit={() => {}}
    />,
  );

  assert.match(markup, /关闭[\s\S]*删除当前服务[\s\S]*编辑当前服务/);
  assert.match(markup, /btn btn--danger btn--sm/);
});

test('模型详情弹框删除中会禁用全部底部操作并显示错误提示', () => {
  const markup = renderToStaticMarkup(
    <AiProviderDetailDialog
      open
      provider={createProvider()}
      adapter={null}
      plugin={null}
      routes={[]}
      locale="zh-CN"
      deleting
      actionError="删除模型服务失败"
      copy={{
        enabled: '已启用',
        disabled: '已停用',
        pluginDisabled: '插件已停用',
        pluginDisabledTitle: '插件不可用',
        pluginDisabledFallback: '请先恢复插件',
        modelNameEmpty: '未填写模型',
        pluginLabel: '来源插件',
        pluginVersionLabel: '插件版本',
        pluginUpdateStateLabel: '更新状态',
        llmWorkflow: '工作流',
        updatedAtLabel: '最近更新',
        summaryRouteTitle: '能力分配',
        summaryRouteEmpty: '暂无能力',
        summaryConfigTitle: '基础配置',
        close: '关闭',
        delete: '删除当前服务',
        deleting: '删除中...',
        edit: '编辑当前服务',
      }}
      onClose={() => {}}
      onDelete={() => {}}
      onEdit={() => {}}
    />,
  );

  assert.match(markup, /删除中\.\.\./);
  assert.match(markup, /settings-note settings-note--error/);
  assert.equal((markup.match(/disabled=""/g) ?? []).length, 3);
});
