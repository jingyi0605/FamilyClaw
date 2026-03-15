import { GuardedPage } from '../../runtime';
import { FamilyLayout } from './LegacyFamilyPage';

export default function FamilyPageH5() {
  return (
    <GuardedPage mode="protected" path="/pages/family/index">
      <div className="family-page-h5" style={{ minHeight: '100vh', background: 'var(--bg-app)' }}>
        <FamilyLayout />
      </div>
    </GuardedPage>
  );
}
