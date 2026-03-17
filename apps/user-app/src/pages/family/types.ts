export type {
  ContextOverviewRead,
  Household,
  Member,
  MemberPreference,
  MemberRelationship,
  RegionNode,
  Room,
} from '@familyclaw/user-core';

import type { Device as CoreDevice } from '@familyclaw/user-core';

export type Device = Omit<CoreDevice, 'status'> & {
  status: CoreDevice['status'] | 'disabled';
};
