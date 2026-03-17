export type DeviceDisplayStatus = 'active' | 'offline' | 'inactive' | 'disabled';
export type DeviceEnabledState = 'enabled' | 'disabled';
export type DeviceStatusBadgeTone = 'success' | 'warning' | 'inactive' | 'danger' | 'secondary';

export function normalizeDeviceDisplayStatus(status: string | null | undefined): DeviceDisplayStatus {
  if (status === 'active' || status === 'offline' || status === 'disabled') {
    return status;
  }
  return 'inactive';
}

export function getDeviceEnabledState(status: string | null | undefined): DeviceEnabledState {
  return normalizeDeviceDisplayStatus(status) === 'disabled' ? 'disabled' : 'enabled';
}

export function getDeviceEnabledBadgeTone(status: string | null | undefined): DeviceStatusBadgeTone {
  return getDeviceEnabledState(status) === 'disabled' ? 'danger' : 'success';
}

export function getDeviceRuntimeBadgeTone(status: string | null | undefined): DeviceStatusBadgeTone {
  const normalizedStatus = normalizeDeviceDisplayStatus(status);
  if (normalizedStatus === 'active') {
    return 'success';
  }
  if (normalizedStatus === 'offline') {
    return 'warning';
  }
  if (normalizedStatus === 'disabled') {
    return 'danger';
  }
  return 'inactive';
}
