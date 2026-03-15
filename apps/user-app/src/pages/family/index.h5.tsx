import { GuardedPage } from '../../runtime';
import { FamilyLayout } from './LegacyFamilyPage';

export default function FamilyPageH5() {
  return (
    <GuardedPage mode="protected" path="/pages/family/index">
      <FamilyLayout />
    </GuardedPage>
  );
}
