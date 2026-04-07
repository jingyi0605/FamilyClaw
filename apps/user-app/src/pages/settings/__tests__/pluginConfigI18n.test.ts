import test from 'node:test';
import assert from 'node:assert/strict';

import {
  resolvePluginConfigSectionDescription,
  resolvePluginConfigSectionTitle,
  resolvePluginConfigSpecDescription,
  resolvePluginConfigSpecTitle,
  resolvePluginConfigSubmitText,
  resolvePluginFieldDescription,
  resolvePluginFieldLabel,
  resolvePluginOptionLabel,
  resolvePluginWidgetHelpText,
  resolvePluginWidgetPlaceholder,
} from '../pluginConfigI18n';
import type {
  PluginManifestConfigField,
  PluginManifestConfigSpec,
  PluginManifestFieldUiSchema,
  PluginManifestUiSection,
} from '../settingsTypes';

function createTranslator(messages: Record<string, string>) {
  return (key: string) => messages[key] ?? key;
}

test('插件配置文案在 key 未命中时会回退到原文', () => {
  const translate = createTranslator({});
  const field: PluginManifestConfigField = {
    key: 'account_label',
    label: '账号标识',
    label_key: 'plugin.demo.field.label',
    description: '用于区分不同账号',
    description_key: 'plugin.demo.field.description',
    type: 'string',
    required: true,
    default: undefined,
    enum_options: [],
  };
  const widget: PluginManifestFieldUiSchema = {
    placeholder: '请输入账号标识',
    placeholder_key: 'plugin.demo.field.placeholder',
    help_text: '保存后用于执行扫码登录',
    help_text_key: 'plugin.demo.field.help',
  };
  const section: PluginManifestUiSection = {
    id: 'basic',
    title: '基础配置',
    title_key: 'plugin.demo.section.title',
    description: '这里先保存账号基础参数',
    description_key: 'plugin.demo.section.description',
    fields: ['account_label'],
  };
  const configSpec: PluginManifestConfigSpec = {
    scope_type: 'plugin',
    title: '微信 Claw 账号配置',
    title_key: 'plugin.demo.title',
    description: '先保存基础参数，再执行扫码登录',
    description_key: 'plugin.demo.description',
    schema_version: 1,
    config_schema: { fields: [field] },
    ui_schema: {
      sections: [section],
      submit_text: '保存微信 Claw 配置',
      submit_text_key: 'plugin.demo.submit',
      widgets: { account_label: widget },
    },
  };

  assert.equal(resolvePluginConfigSpecTitle(configSpec, translate), '微信 Claw 账号配置');
  assert.equal(resolvePluginConfigSpecDescription(configSpec, translate), '先保存基础参数，再执行扫码登录');
  assert.equal(resolvePluginConfigSectionTitle(section, translate), '基础配置');
  assert.equal(resolvePluginConfigSectionDescription(section, translate), '这里先保存账号基础参数');
  assert.equal(resolvePluginFieldLabel(field, translate), '账号标识');
  assert.equal(resolvePluginFieldDescription(field, translate), '用于区分不同账号');
  assert.equal(resolvePluginWidgetPlaceholder(widget, translate), '请输入账号标识');
  assert.equal(resolvePluginWidgetHelpText(widget, field, translate), '保存后用于执行扫码登录');
  assert.equal(
    resolvePluginOptionLabel({ label: '稳定模式', label_key: 'plugin.demo.option.stable', value: 'stable' }, translate),
    '稳定模式',
  );
  assert.equal(resolvePluginConfigSubmitText(configSpec, translate), '保存微信 Claw 配置');
});
