import { CoreApiClient } from '../api';
import { MemberGuideStatus } from '../domain/types';

export async function loadMemberGuideStatus(
  client: Pick<CoreApiClient, 'getMemberGuideStatus'>,
  memberId: string,
): Promise<MemberGuideStatus | null> {
  if (!memberId) {
    return null;
  }

  return client.getMemberGuideStatus(memberId);
}
