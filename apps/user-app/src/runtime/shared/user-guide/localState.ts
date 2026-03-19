import type { KeyValueStorage } from '@familyclaw/user-platform';
import { USER_GUIDE_AUTO_START_STORAGE_KEY, USER_GUIDE_SESSION_STORAGE_KEY } from './constants';

type PendingGuideLaunchPayload = {
  source: 'auto_after_setup';
  created_at: string;
};

export type UserGuideSessionCheckpoint = {
  manifest_version: number;
  current_step_index: number;
  source: 'auto_after_setup' | 'manual';
  updated_at: string;
};

export async function markPendingGuideAutoStart(storage: KeyValueStorage) {
  const payload: PendingGuideLaunchPayload = {
    source: 'auto_after_setup',
    created_at: new Date().toISOString(),
  };

  await storage.setItem(USER_GUIDE_AUTO_START_STORAGE_KEY, JSON.stringify(payload));
}

export async function clearPendingGuideAutoStart(storage: KeyValueStorage) {
  await storage.removeItem(USER_GUIDE_AUTO_START_STORAGE_KEY);
}

function parsePendingGuideLaunchPayload(rawValue: string): PendingGuideLaunchPayload | null {
  try {
    const parsed = JSON.parse(rawValue) as Partial<PendingGuideLaunchPayload> | null;
    if (!parsed || parsed.source !== 'auto_after_setup') {
      return null;
    }

    return {
      source: 'auto_after_setup',
      created_at: typeof parsed.created_at === 'string' ? parsed.created_at : '',
    };
  } catch {
    return null;
  }
}

export async function readPendingGuideAutoStart(storage: KeyValueStorage): Promise<PendingGuideLaunchPayload | null> {
  const rawValue = await storage.getItem(USER_GUIDE_AUTO_START_STORAGE_KEY);
  if (!rawValue) {
    return null;
  }

  return parsePendingGuideLaunchPayload(rawValue);
}

export async function consumePendingGuideAutoStart(storage: KeyValueStorage): Promise<PendingGuideLaunchPayload | null> {
  const rawValue = await storage.getItem(USER_GUIDE_AUTO_START_STORAGE_KEY);
  if (!rawValue) {
    return null;
  }

  await storage.removeItem(USER_GUIDE_AUTO_START_STORAGE_KEY);
  return parsePendingGuideLaunchPayload(rawValue);
}

export async function saveGuideSessionCheckpoint(
  storage: KeyValueStorage,
  checkpoint: UserGuideSessionCheckpoint,
) {
  await storage.setItem(USER_GUIDE_SESSION_STORAGE_KEY, JSON.stringify(checkpoint));
}

export async function clearGuideSessionCheckpoint(storage: KeyValueStorage) {
  await storage.removeItem(USER_GUIDE_SESSION_STORAGE_KEY);
}

export async function readGuideSessionCheckpoint(storage: KeyValueStorage): Promise<UserGuideSessionCheckpoint | null> {
  const rawValue = await storage.getItem(USER_GUIDE_SESSION_STORAGE_KEY);
  if (!rawValue) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawValue) as Partial<UserGuideSessionCheckpoint> | null;
    if (
      !parsed
      || typeof parsed.manifest_version !== 'number'
      || typeof parsed.current_step_index !== 'number'
      || (parsed.source !== 'auto_after_setup' && parsed.source !== 'manual')
    ) {
      return null;
    }

    return {
      manifest_version: parsed.manifest_version,
      current_step_index: parsed.current_step_index,
      source: parsed.source,
      updated_at: typeof parsed.updated_at === 'string' ? parsed.updated_at : '',
    };
  } catch {
    return null;
  }
}
