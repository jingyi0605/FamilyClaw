import test from 'node:test';
import assert from 'node:assert/strict';

import {
  MARKETPLACE_CONFIRM_CLICK_GUARD_MS,
  isMarketplaceConfirmClickGuardActive,
  isMarketplaceInstallActionBusy,
  isMarketplaceInstanceActionBusy,
} from '../marketplaceConfirmGuard';

test('确认弹窗未打开时，不启用点击保护', () => {
  assert.equal(isMarketplaceConfirmClickGuardActive(null, 1000), false);
});

test('确认弹窗刚打开时，保护窗仍然生效', () => {
  assert.equal(isMarketplaceConfirmClickGuardActive(1000, 1000), true);
  assert.equal(
    isMarketplaceConfirmClickGuardActive(1000, 1000 + MARKETPLACE_CONFIRM_CLICK_GUARD_MS - 1),
    true,
  );
});

test('超过保护时间后，确认按钮才允许点击', () => {
  assert.equal(
    isMarketplaceConfirmClickGuardActive(1000, 1000 + MARKETPLACE_CONFIRM_CLICK_GUARD_MS),
    false,
  );
});

test('安装按钮忙状态只认完全匹配的安装 key', () => {
  assert.equal(isMarketplaceInstallActionBusy('source-1', 'plugin-a', 'source-1:plugin-a'), true);
  assert.equal(isMarketplaceInstallActionBusy('source-1', 'plugin-a', null), false);
  assert.equal(isMarketplaceInstallActionBusy('source-1', 'plugin-a', 'source-1:plugin-b'), false);
});

test('实例忙状态要求两边都有非空 instance_id，不能把 null === null 当成忙', () => {
  assert.equal(isMarketplaceInstanceActionBusy(null, null), false);
  assert.equal(isMarketplaceInstanceActionBusy(null, 'instance-1'), false);
  assert.equal(isMarketplaceInstanceActionBusy('instance-1', null), false);
  assert.equal(isMarketplaceInstanceActionBusy('instance-1', 'instance-1'), true);
  assert.equal(isMarketplaceInstanceActionBusy('instance-1', 'instance-2'), false);
});
