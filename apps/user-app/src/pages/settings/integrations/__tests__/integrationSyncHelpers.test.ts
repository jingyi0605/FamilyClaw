import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildSyncAllImpactSummary,
  filterIntegrationDeviceCandidates,
  getCandidateDomainOptions,
  getCandidateEntityDomain,
  getCandidateRoomOptions,
  type IntegrationDeviceCandidate,
} from '../integrationSyncHelpers';
import {
  resolvePluginConfigSectionDescription,
  resolvePluginConfigSectionTitle,
  resolvePluginConfigSpecDescription,
  resolvePluginConfigSpecTitle,
  resolvePluginConfigSubmitText,
  resolvePluginFieldDescription,
  resolvePluginFieldLabel,
  resolvePluginMaybeKey,
  resolvePluginOptionLabel,
  resolvePluginWidgetHelpText,
  resolvePluginWidgetPlaceholder,
} from '../../pluginConfigI18n';
import type {
  PluginManifestConfigField,
  PluginManifestConfigSpec,
  PluginManifestFieldUiSchema,
  PluginManifestUiSection,
} from '../../settingsTypes';

function createCandidate(
  overrides: Partial<IntegrationDeviceCandidate> = {},
): IntegrationDeviceCandidate {
  return {
    external_device_id: 'device-1',
    primary_entity_id: 'light.living_room_main',
    name: '客厅主灯',
    room_name: '客厅',
    entity_count: 2,
    already_synced: false,
    ...overrides,
  };
}

test('实体域提取只返回合法 entity_id 的 domain', () => {
  assert.equal(getCandidateEntityDomain(createCandidate()), 'light');
  assert.equal(getCandidateEntityDomain(createCandidate({ primary_entity_id: 'switch.ac' })), 'switch');
  assert.equal(getCandidateEntityDomain(createCandidate({ primary_entity_id: 'invalid-entity-id' })), null);
  assert.equal(getCandidateEntityDomain(createCandidate({ primary_entity_id: null })), null);
});

test('候选房间和实体域选项会去重并按字母排序', () => {
  const candidates = [
    createCandidate({ external_device_id: 'device-1', room_name: '主卧', primary_entity_id: 'switch.bedroom' }),
    createCandidate({ external_device_id: 'device-2', room_name: '客厅', primary_entity_id: 'light.living_room' }),
    createCandidate({ external_device_id: 'device-3', room_name: '客厅', primary_entity_id: 'sensor.air_quality' }),
    createCandidate({ external_device_id: 'device-4', room_name: null, primary_entity_id: null }),
  ];

  assert.deepEqual(getCandidateRoomOptions(candidates), ['客厅', '主卧']);
  assert.deepEqual(getCandidateDomainOptions(candidates), ['light', 'sensor', 'switch']);
});

test('候选筛选支持名称搜索、房间筛选和实体域筛选叠加', () => {
  const candidates = [
    createCandidate({
      external_device_id: 'device-1',
      name: '客厅主灯',
      room_name: '客厅',
      primary_entity_id: 'light.living_room_main',
    }),
    createCandidate({
      external_device_id: 'device-2',
      name: '主卧空调',
      room_name: '主卧',
      primary_entity_id: 'climate.bedroom_ac',
    }),
    createCandidate({
      external_device_id: 'device-3',
      name: '客厅温湿度',
      room_name: '客厅',
      primary_entity_id: 'sensor.living_room_climate',
    }),
  ];

  assert.deepEqual(
    filterIntegrationDeviceCandidates(candidates, {
      keyword: '  客厅  ',
      room: 'all',
      domain: 'all',
    }).map((item) => item.external_device_id),
    ['device-1', 'device-3'],
  );

  assert.deepEqual(
    filterIntegrationDeviceCandidates(candidates, {
      keyword: '空调',
      room: '主卧',
      domain: 'climate',
    }).map((item) => item.external_device_id),
    ['device-2'],
  );

  assert.deepEqual(
    filterIntegrationDeviceCandidates(candidates, {
      keyword: '客厅',
      room: '客厅',
      domain: 'sensor',
    }).map((item) => item.external_device_id),
    ['device-3'],
  );
});

test('全量同步影响摘要会区分已同步和新增设备数量', () => {
  const summary = buildSyncAllImpactSummary([
    createCandidate({ external_device_id: 'device-1', already_synced: true }),
    createCandidate({ external_device_id: 'device-2', already_synced: false }),
    createCandidate({ external_device_id: 'device-3', already_synced: true }),
    createCandidate({ external_device_id: 'device-4', already_synced: false }),
  ]);

  assert.deepEqual(summary, {
    total: 4,
    alreadySynced: 2,
    newCount: 2,
  });
});

function createTranslator(messages: Record<string, string>) {
  return (key: string) => messages[key] ?? key;
}

test('插件配置文案优先走 key，没命中时回退原文', () => {
  const translate = createTranslator({
    'plugin.demo.title': '演示插件配置',
    'plugin.demo.description': '这是翻译后的配置说明',
    'plugin.demo.section.title': '基础设置',
    'plugin.demo.section.description': '先把基础项配好',
    'plugin.demo.field.label': '接口地址',
    'plugin.demo.field.description': '这是接口根地址',
    'plugin.demo.field.help': '会拼接到实际请求里',
    'plugin.demo.field.placeholder': '请输入接口地址',
    'plugin.demo.option.strict': '严格模式',
    'plugin.demo.submit': '保存演示配置',
    'plugin.demo.rawError': '这是翻译后的错误',
  });

  const field: PluginManifestConfigField = {
    key: 'base_url',
    label: '基础地址',
    label_key: 'plugin.demo.field.label',
    description: '原始说明',
    description_key: 'plugin.demo.field.description',
    type: 'string',
    required: true,
    default: undefined,
    enum_options: [],
  };
  const widget: PluginManifestFieldUiSchema = {
    placeholder: '原始占位',
    placeholder_key: 'plugin.demo.field.placeholder',
    help_text: '原始帮助',
    help_text_key: 'plugin.demo.field.help',
  };
  const section: PluginManifestUiSection = {
    id: 'basic',
    title: '原始 section 标题',
    title_key: 'plugin.demo.section.title',
    description: '原始 section 说明',
    description_key: 'plugin.demo.section.description',
    fields: ['base_url'],
  };
  const configSpec: PluginManifestConfigSpec = {
    scope_type: 'plugin',
    title: '原始标题',
    title_key: 'plugin.demo.title',
    description: '原始描述',
    description_key: 'plugin.demo.description',
    schema_version: 1,
    config_schema: { fields: [field] },
    ui_schema: {
      sections: [section],
      field_order: ['base_url'],
      submit_text: '原始保存',
      submit_text_key: 'plugin.demo.submit',
      widgets: { base_url: widget },
    },
  };

  assert.equal(resolvePluginConfigSpecTitle(configSpec, translate), '演示插件配置');
  assert.equal(resolvePluginConfigSpecDescription(configSpec, translate), '这是翻译后的配置说明');
  assert.equal(resolvePluginConfigSectionTitle(section, translate), '基础设置');
  assert.equal(resolvePluginConfigSectionDescription(section, translate), '先把基础项配好');
  assert.equal(resolvePluginFieldLabel(field, translate), '接口地址');
  assert.equal(resolvePluginFieldDescription(field, translate), '这是接口根地址');
  assert.equal(resolvePluginWidgetPlaceholder(widget, translate), '请输入接口地址');
  assert.equal(resolvePluginWidgetHelpText(widget, field, translate), '会拼接到实际请求里');
  assert.equal(
    resolvePluginOptionLabel({ label: '原始选项', label_key: 'plugin.demo.option.strict', value: 'strict' }, translate),
    '严格模式',
  );
  assert.equal(resolvePluginConfigSubmitText(configSpec, translate), '保存演示配置');
  assert.equal(resolvePluginMaybeKey('plugin.demo.rawError', translate), '这是翻译后的错误');
});

test('插件配置文案 key 缺失时会稳妥回退到原文', () => {
  const translate = createTranslator({});
  const field: PluginManifestConfigField = {
    key: 'token',
    label: '访问令牌',
    type: 'secret',
    required: false,
    description: '这里填写访问令牌',
    default: undefined,
    enum_options: [],
  };
  const widget: PluginManifestFieldUiSchema = {
    placeholder: '请输入访问令牌',
  };
  const section: PluginManifestUiSection = {
    id: 'auth',
    title: '认证信息',
    description: '没有 key 时就显示原文',
    fields: ['token'],
  };
  const configSpec: PluginManifestConfigSpec = {
    scope_type: 'plugin',
    title: '插件设置',
    description: '原文描述',
    schema_version: 1,
    config_schema: { fields: [field] },
    ui_schema: {
      sections: [section],
      submit_text: '保存设置',
      widgets: { token: widget },
    },
  };

  assert.equal(resolvePluginConfigSpecTitle(configSpec, translate), '插件设置');
  assert.equal(resolvePluginConfigSpecDescription(configSpec, translate), '原文描述');
  assert.equal(resolvePluginConfigSectionTitle(section, translate), '认证信息');
  assert.equal(resolvePluginConfigSectionDescription(section, translate), '没有 key 时就显示原文');
  assert.equal(resolvePluginFieldLabel(field, translate), '访问令牌');
  assert.equal(resolvePluginFieldDescription(field, translate), '这里填写访问令牌');
  assert.equal(resolvePluginWidgetPlaceholder(widget, translate), '请输入访问令牌');
  assert.equal(resolvePluginWidgetHelpText(undefined, field, translate), '这里填写访问令牌');
  assert.equal(resolvePluginConfigSubmitText(configSpec, translate), '保存设置');
  assert.equal(resolvePluginMaybeKey('  直接报错文本  ', translate), '直接报错文本');
});
