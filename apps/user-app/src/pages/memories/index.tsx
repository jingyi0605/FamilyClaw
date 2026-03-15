import { GuardedPage } from '../../runtime';
import { MemoriesPageImpl } from './MemoriesPageImpl';

export default function MemoriesPage() {
  return (
    <GuardedPage mode="protected" path="/pages/memories/index">
      <MemoriesPageImpl />
    </GuardedPage>
  );
}
