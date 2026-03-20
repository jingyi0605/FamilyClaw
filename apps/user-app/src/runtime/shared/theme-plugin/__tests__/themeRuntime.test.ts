import assert from 'node:assert/strict';
import test from 'node:test';
import { createThemeRuntime } from '../themeRuntime';
import type {
  BuiltinThemeBundleEntry,
  PluginThemeRegistrySnapshotRead,
  PluginThemeResourceRead,
} from '../types';

function createBuiltinEntry(overrides: Partial<BuiltinThemeBundleEntry> = {}): BuiltinThemeBundleEntry {
  return {
    plugin_id: 'builtin.theme.chun-he-jing-ming',
    theme_id: 'chun-he-jing-ming',
    display_name: '春和景明',
    description: '默认内置主题',
    source_type: 'builtin',
    resource_source: 'builtin_bundle',
    resource_version: '1.0.0',
    theme_schema_version: 1,
    platform_targets: ['h5', 'rn'],
    bundle_module: './bundles/builtin.theme.chun-he-jing-ming/chun-he-jing-ming',
    load_bundle: async () => ({
      tokens: {
        bgApp: '#f7f5f2',
        bgCard: '#ffffff',
        brandPrimary: '#d97756',
        textPrimary: '#1a1a1a',
        glowColor: 'rgba(217, 119, 86, 0.2)',
      },
      display_name: '春和景明',
      description: '默认内置主题',
    }),
    ...overrides,
  };
}

function createRuntime(options: {
  builtinEntries?: BuiltinThemeBundleEntry[];
  fetchRegistry?: (householdId: string) => Promise<PluginThemeRegistrySnapshotRead>;
  fetchResource?: (
    householdId: string,
    pluginId: string,
    themeId: string,
  ) => Promise<PluginThemeResourceRead>;
  readStoredSelection?: () => { plugin_id: string; theme_id: string } | null;
}) {
  return createThemeRuntime({
    builtinEntries: options.builtinEntries ?? [createBuiltinEntry()],
    fetchRegistry: options.fetchRegistry ?? (async () => ({ items: [] })),
    fetchResource: options.fetchResource ?? (async () => ({
      plugin_id: 'builtin.theme.chun-he-jing-ming',
      theme_id: 'chun-he-jing-ming',
      resource_version: '1.0.0',
      theme_schema_version: 1,
      tokens: {
        bgApp: '#f7f5f2',
        bgCard: '#ffffff',
        brandPrimary: '#d97756',
        textPrimary: '#1a1a1a',
        glowColor: 'rgba(217, 119, 86, 0.2)',
      },
    })),
    readStoredSelection: options.readStoredSelection ?? (() => null),
    writeStoredSelection: () => undefined,
  });
}

test('登录前启动仅使用内置主题插件链路', async () => {
  let fetchRegistryCallCount = 0;
  const runtime = createRuntime({
    fetchRegistry: async () => {
      fetchRegistryCallCount += 1;
      return { items: [] };
    },
  });

  await runtime.bootstrap();
  const state = runtime.getState();

  assert.equal(fetchRegistryCallCount, 0);
  assert.equal(state.status, 'ready');
  assert.equal(state.active_theme?.id, 'chun-he-jing-ming');
  assert.equal(state.active_theme?.plugin_id, 'builtin.theme.chun-he-jing-ming');
});

test('拿到家庭上下文后可加载远端主题插件资源', async () => {
  let fetchResourceCallCount = 0;
  const runtime = createRuntime({
    fetchRegistry: async () => ({
      items: [
        {
          plugin_id: 'third.party.theme.aurora',
          theme_id: 'aurora',
          display_name: '极光',
          resource_source: 'managed_plugin_dir',
          resource_version: '2.0.0',
          theme_schema_version: 1,
          source_type: 'third_party',
          state: 'ready',
          enabled: true,
        },
      ],
    }),
    fetchResource: async () => {
      fetchResourceCallCount += 1;
      return {
        plugin_id: 'third.party.theme.aurora',
        theme_id: 'aurora',
        resource_version: '2.0.0',
        theme_schema_version: 1,
        tokens: {
          bgApp: '#0b1220',
          bgCard: '#0f1a2d',
          brandPrimary: '#4d8dff',
          textPrimary: '#f5f7ff',
          glowColor: 'rgba(77, 141, 255, 0.25)',
        },
      };
    },
  });

  await runtime.bootstrap();
  await runtime.refreshRegistry('household-1');
  await runtime.selectThemeByThemeId('aurora');
  const state = runtime.getState();

  assert.equal(fetchResourceCallCount, 1);
  assert.equal(state.status, 'ready');
  assert.equal(state.active_theme?.id, 'aurora');
  assert.equal(state.active_theme?.plugin_id, 'third.party.theme.aurora');
});

test('已选主题插件失效时进入 missing 状态且不静默回退', async () => {
  const runtime = createRuntime({});

  await runtime.bootstrap();
  await runtime.selectTheme({
    plugin_id: 'third.party.theme.aurora',
    theme_id: 'aurora',
  });
  const state = runtime.getState();

  assert.equal(state.status, 'missing');
  assert.equal(state.selection?.theme_id, 'aurora');
  assert.equal(state.missing_selection?.theme_id, 'aurora');
  assert.equal(state.active_theme, null);
  assert.equal(state.theme_fallback_notice?.disabledThemeId, 'aurora');
});

test('已选主题被禁用时保留待重选状态并返回禁用原因', async () => {
  const runtime = createRuntime({
    readStoredSelection: () => ({
      plugin_id: 'third.party.theme.aurora',
      theme_id: 'aurora',
    }),
    fetchRegistry: async () => ({
      items: [
        {
          plugin_id: 'third.party.theme.aurora',
          theme_id: 'aurora',
          display_name: '极光',
          resource_source: 'managed_plugin_dir',
          resource_version: '2.0.0',
          theme_schema_version: 1,
          source_type: 'third_party',
          state: 'disabled',
          enabled: false,
          disabled_reason: 'plugin_disabled_by_household',
        },
      ],
    }),
  });

  await runtime.bootstrap();
  await runtime.refreshRegistry('household-1');
  const state = runtime.getState();

  assert.equal(state.status, 'missing');
  assert.equal(state.selection?.plugin_id, 'third.party.theme.aurora');
  assert.equal(state.theme_fallback_notice?.disabledReason, 'plugin_disabled_by_household');
  assert.equal(state.disabled_reason_by_theme_id.aurora, 'plugin_disabled_by_household');
});

test('主题列表顺序固定，不会因为切换选中项而重排', async () => {
  const runtime = createRuntime({
    builtinEntries: [
      createBuiltinEntry({
        plugin_id: 'builtin.theme.chun-he-jing-ming',
        theme_id: 'chun-he-jing-ming',
        display_name: '春和景明',
      }),
      createBuiltinEntry({
        plugin_id: 'builtin.theme.yue-lang-xing-xi',
        theme_id: 'yue-lang-xing-xi',
        display_name: '月朗星稀',
      }),
      createBuiltinEntry({
        plugin_id: 'builtin.theme.feng-chi-dian-che',
        theme_id: 'feng-chi-dian-che',
        display_name: '风驰电掣',
      }),
    ],
    fetchResource: async (_, pluginId, themeId) => ({
      plugin_id: pluginId,
      theme_id: themeId,
      resource_version: '1.0.0',
      theme_schema_version: 1,
      tokens: {
        bgApp: '#111111',
        bgCard: '#222222',
        brandPrimary: '#333333',
        textPrimary: '#ffffff',
        glowColor: 'rgba(0, 0, 0, 0.2)',
      },
    }),
  });

  await runtime.bootstrap();
  assert.deepEqual(
    runtime.getState().theme_list.map(theme => theme.id),
    ['chun-he-jing-ming', 'yue-lang-xing-xi', 'feng-chi-dian-che'],
  );

  await runtime.selectTheme({
    plugin_id: 'builtin.theme.feng-chi-dian-che',
    theme_id: 'feng-chi-dian-che',
  });

  assert.deepEqual(
    runtime.getState().theme_list.map(theme => theme.id),
    ['chun-he-jing-ming', 'yue-lang-xing-xi', 'feng-chi-dian-che'],
  );
});
