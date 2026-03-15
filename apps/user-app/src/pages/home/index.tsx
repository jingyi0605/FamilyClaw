import HomePage from './page';
import { GuardedPage } from '../../runtime';

export default function GuardedHomePage() {
  return (
    <GuardedPage mode="protected" path="/pages/home/index">
      <HomePage />
    </GuardedPage>
  );
}
