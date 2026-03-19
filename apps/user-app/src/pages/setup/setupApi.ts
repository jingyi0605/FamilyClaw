import { createCoreApiClient, createRequestClient } from '@familyclaw/user-core';
import type {
  AgentDetail,
  AiCapability,
  AiCapabilityRoute,
  AiCapabilityRouteUpsertPayload,
  AiProviderAdapter,
  AiProviderModelDiscoveryPayload,
  AiProviderModelDiscoveryResult,
  AiProviderProfile,
  AiProviderProfileCreatePayload,
  AiProviderProfileUpdatePayload,
  ButlerBootstrapSession,
} from './setupTypes';

const request = createRequestClient({
  baseUrl: '/api/v1',
  credentials: 'include',
});

const coreApi = createCoreApiClient(request);

export const setupApi = {
  ...coreApi,
  listAiProviderAdapters(householdId: string) {
    return request<AiProviderAdapter[]>(`/ai-config/${encodeURIComponent(householdId)}/provider-adapters`);
  },
  discoverAiProviderModels(householdId: string, adapterCode: string, payload: AiProviderModelDiscoveryPayload) {
    return request<AiProviderModelDiscoveryResult>(`/ai-config/${encodeURIComponent(householdId)}/provider-adapters/${encodeURIComponent(adapterCode)}/discover-models`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  listHouseholdAiProviders(householdId: string) {
    return request<AiProviderProfile[]>(`/ai-config/${encodeURIComponent(householdId)}/provider-profiles`);
  },
  createHouseholdAiProvider(householdId: string, payload: AiProviderProfileCreatePayload) {
    return request<AiProviderProfile>(`/ai-config/${encodeURIComponent(householdId)}/provider-profiles`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  updateHouseholdAiProvider(householdId: string, profileId: string, payload: AiProviderProfileUpdatePayload) {
    return request<AiProviderProfile>(`/ai-config/${encodeURIComponent(householdId)}/provider-profiles/${encodeURIComponent(profileId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
  listHouseholdAiRoutes(householdId: string) {
    return request<AiCapabilityRoute[]>(`/ai-config/${encodeURIComponent(householdId)}/provider-routes`);
  },
  upsertHouseholdAiRoute(householdId: string, capability: AiCapability, payload: AiCapabilityRouteUpsertPayload) {
    return request<AiCapabilityRoute>(`/ai-config/${encodeURIComponent(householdId)}/provider-routes/${encodeURIComponent(capability)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
  createButlerBootstrapSession(householdId: string) {
    return request<ButlerBootstrapSession>(`/ai-config/${encodeURIComponent(householdId)}/butler-bootstrap/sessions`, { method: 'POST' }, 60000);
  },
  getLatestButlerBootstrapSession(householdId: string) {
    return request<ButlerBootstrapSession | null>(`/ai-config/${encodeURIComponent(householdId)}/butler-bootstrap/sessions/latest`, { method: 'GET' }, 60000);
  },
  restartButlerBootstrapSession(householdId: string) {
    return request<ButlerBootstrapSession>(`/ai-config/${encodeURIComponent(householdId)}/butler-bootstrap/sessions/restart`, { method: 'POST' }, 60000);
  },
  confirmButlerBootstrapSession(householdId: string, sessionId: string, payload: { draft: ButlerBootstrapSession['draft']; created_by?: string }) {
    return request<AgentDetail>(`/ai-config/${encodeURIComponent(householdId)}/butler-bootstrap/sessions/${encodeURIComponent(sessionId)}/confirm`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};
