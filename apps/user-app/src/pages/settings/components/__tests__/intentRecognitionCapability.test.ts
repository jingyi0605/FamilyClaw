import test from 'node:test';
import assert from 'node:assert/strict';

import { getCapabilityLabel, AI_CAPABILITY_OPTIONS } from '../../../setup/setupAiConfig';

test('意图识别能力会出现在能力选项里并带有人话标签', () => {
  const values = AI_CAPABILITY_OPTIONS.map(item => item.value);

  assert.ok(values.includes('intent_recognition'));
  assert.equal(getCapabilityLabel('intent_recognition', 'zh-CN'), '意图识别');
  assert.equal(getCapabilityLabel('intent_recognition', 'en-US'), 'Intent recognition');
});
