import HomePage from './page.rn';
import { GuardedPage } from '../../runtime/index.rn';

export default function GuardedHomePage() {
  return (
    <GuardedPage mode="protected" path="/pages/home/index">
      <HomePage />
    </GuardedPage>
  );
}
