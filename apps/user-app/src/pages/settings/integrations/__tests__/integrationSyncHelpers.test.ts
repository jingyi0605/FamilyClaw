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
