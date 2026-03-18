import test from 'node:test';
import assert from 'node:assert/strict';

import { shouldBlockDisableCurrentThemePlugin } from '../pluginStateGuards';

type TestPlugin = Parameters<typeof shouldBlockDisableCurrentThemePlugin>[0];

function createPlugin(overrides: Partial<TestPlugin> = {}): TestPlugin {
  return {
    id: 'builtin.theme.chun-he-jing-ming',
    enabled: true,
    types: ['theme-pack'],
    ...overrides,
  };
}

test('当前正在使用的主题插件在停用前会被拦截', () => {
  assert.equal(
    shouldBlockDisableCurrentThemePlugin(
      createPlugin(),
      'builtin.theme.chun-he-jing-ming',
    ),
    true,
  );
});

test('非当前主题插件或非主题插件不会被这条规则拦截', () => {
  assert.equal(
    shouldBlockDisableCurrentThemePlugin(
      createPlugin({ id: 'builtin.theme.yue-lang-xing-xi' }),
      'builtin.theme.chun-he-jing-ming',
    ),
    false,
  );
  assert.equal(
    shouldBlockDisableCurrentThemePlugin(
      createPlugin({ id: 'builtin.locale.zh-cn', types: ['locale-pack'] }),
      'builtin.theme.chun-he-jing-ming',
    ),
    false,
  );
  assert.equal(
    shouldBlockDisableCurrentThemePlugin(
      createPlugin({ enabled: false }),
      'builtin.theme.chun-he-jing-ming',
    ),
    false,
  );
});
