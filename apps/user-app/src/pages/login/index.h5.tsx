import { GuardedPage } from '../../runtime';
import { H5LoginPage } from '../../runtime/h5-shell';

export default function LoginPageH5() {
  return (
    <GuardedPage mode="login" path="/pages/login/index">
      <H5LoginPage />
    </GuardedPage>
  );
}
