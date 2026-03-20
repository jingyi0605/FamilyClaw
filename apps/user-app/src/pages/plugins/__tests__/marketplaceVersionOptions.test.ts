import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getDefaultMarketplaceVersionSelection,
  isMarketplaceVersionActionable,
  resolveMarketplaceVersionActionStatusKey,
  resolveMarketplaceVersionOptionByVersion,
} from '../marketplaceVersionOptions';
import type { MarketplaceVersionOptionsRead } from '../../settings/settingsTypes';

function createOptions(overrides: Partial<MarketplaceVersionOptionsRead> = {}): MarketplaceVersionOptionsRead {
  return {
    source_id: 'source-001',
    plugin_id: 'demo-plugin',
    installed_version: '1.0.0',
    latest_version: '2.0.0',
    latest_compatible_version: '1.1.0',
    items: [
      {
        version: '1.1.0',
        git_ref: 'refs/tags/v1.1.0',
        artifact_type: 'source_archive',
        artifact_url: 'https://example.com/demo-plugin-1.1.0.zip',
        checksum: null,
        published_at: null,
        min_app_version: '0.1.0',
        is_latest: false,
        is_latest_compatible: true,
        is_installed: false,
        compatibility_status: 'compatible',
        blocked_reason: null,
        action: 'upgrade',
        can_install: false,
        can_switch: true,
      },
      {
        version: '1.0.0',
        git_ref: 'refs/tags/v1.0.0',
        artifact_type: 'source_archive',
        artifact_url: 'https://example.com/demo-plugin-1.0.0.zip',
        checksum: null,
        published_at: null,
        min_app_version: '0.1.0',
        is_latest: false,
        is_latest_compatible: false,
        is_installed: true,
        compatibility_status: 'compatible',
        blocked_reason: null,
        action: 'current',
        can_install: false,
        can_switch: false,
      },
    ],
    ...overrides,
  };
}

test('已安装插件默认高亮当前版本', () => {
  assert.equal(getDefaultMarketplaceVersionSelection(createOptions()), '1.0.0');
});

test('未安装插件默认高亮最新可兼容版本，没有可兼容版本时不选中', () => {
  const notInstalled = createOptions({
    installed_version: null,
    items: createOptions().items.map(item => ({
      ...item,
      is_installed: false,
      action: item.version === '1.1.0' ? 'install' : 'unavailable',
      can_install: item.version === '1.1.0',
      can_switch: false,
    })),
  });
  assert.equal(getDefaultMarketplaceVersionSelection(notInstalled), '1.1.0');

  const noCompatible = createOptions({
    installed_version: null,
    latest_compatible_version: null,
    items: notInstalled.items.map(item => ({
      ...item,
      is_latest_compatible: false,
      action: 'unavailable',
      can_install: false,
    })),
  });
  assert.equal(getDefaultMarketplaceVersionSelection(noCompatible), '');
});

test('只有 install upgrade rollback 算可执行动作', () => {
  assert.equal(isMarketplaceVersionActionable('install'), true);
  assert.equal(isMarketplaceVersionActionable('upgrade'), true);
  assert.equal(isMarketplaceVersionActionable('rollback'), true);
  assert.equal(isMarketplaceVersionActionable('current'), false);
  assert.equal(isMarketplaceVersionActionable('unavailable'), false);
});

test('状态消息 key 和版本项查找走后端 action，不做前端版本比较', () => {
  assert.equal(resolveMarketplaceVersionActionStatusKey('install'), 'plugins.marketplace.status.installed');
  assert.equal(resolveMarketplaceVersionActionStatusKey('upgrade'), 'plugins.marketplace.status.upgraded');
  assert.equal(resolveMarketplaceVersionActionStatusKey('rollback'), 'plugins.marketplace.status.rolledBack');
  assert.equal(resolveMarketplaceVersionActionStatusKey('current'), null);

  const options = createOptions();
  assert.equal(resolveMarketplaceVersionOptionByVersion(options, '1.1.0')?.action, 'upgrade');
  assert.equal(resolveMarketplaceVersionOptionByVersion(options, '9.9.9'), null);
});
