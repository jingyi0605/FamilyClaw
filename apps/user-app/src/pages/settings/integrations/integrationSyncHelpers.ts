export type IntegrationDeviceCandidate = {
  external_device_id: string;
  primary_entity_id?: string | null;
  name: string;
  room_name: string | null;
  entity_count: number;
  already_synced: boolean;
};

export type SyncAllImpactSummary = {
  total: number;
  alreadySynced: number;
  newCount: number;
};

export type IntegrationDeviceCandidateFilters = {
  keyword: string;
  room: string;
  domain: string;
};

export function getCandidateEntityDomain(candidate: IntegrationDeviceCandidate): string | null {
  const entityId = candidate.primary_entity_id?.trim();
  if (!entityId || !entityId.includes('.')) {
    return null;
  }
  return entityId.split('.')[0] ?? null;
}

export function getCandidateRoomOptions(candidates: IntegrationDeviceCandidate[]): string[] {
  return Array.from(
    new Set(
      candidates
        .map((item) => item.room_name?.trim())
        .filter((item): item is string => Boolean(item)),
    ),
  ).sort((left, right) => left.localeCompare(right));
}

export function getCandidateDomainOptions(candidates: IntegrationDeviceCandidate[]): string[] {
  return Array.from(
    new Set(
      candidates
        .map(getCandidateEntityDomain)
        .filter((item): item is string => Boolean(item)),
    ),
  ).sort((left, right) => left.localeCompare(right));
}

export function filterIntegrationDeviceCandidates(
  candidates: IntegrationDeviceCandidate[],
  filters: IntegrationDeviceCandidateFilters,
): IntegrationDeviceCandidate[] {
  const normalizedKeyword = filters.keyword.trim().toLowerCase();
  return candidates.filter((candidate) => {
    if (normalizedKeyword && !candidate.name.toLowerCase().includes(normalizedKeyword)) {
      return false;
    }
    if (filters.room !== 'all' && candidate.room_name !== filters.room) {
      return false;
    }
    const entityDomain = getCandidateEntityDomain(candidate);
    if (filters.domain !== 'all' && entityDomain !== filters.domain) {
      return false;
    }
    return true;
  });
}

export function buildSyncAllImpactSummary(
  candidates: IntegrationDeviceCandidate[],
): SyncAllImpactSummary {
  const alreadySynced = candidates.filter((item) => item.already_synced).length;
  return {
    total: candidates.length,
    alreadySynced,
    newCount: Math.max(candidates.length - alreadySynced, 0),
  };
}
