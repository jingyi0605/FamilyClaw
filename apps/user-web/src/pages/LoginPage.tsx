import { useState, type FormEvent } from 'react';

import { useAuthContext } from '../state/auth';

export function LoginPage() {
  const { login, loginPending, loginError } = useAuthContext();
  const [username, setUsername] = useState('user');
  const [password, setPassword] = useState('user');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await login(username.trim(), password);
    } catch {
      return;
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-screen__panel auth-screen__panel--hero">
        <span className="auth-screen__kicker">FamilyClaw Home</span>
        <h1>先登录，再进家庭空间</h1>
        <p>
          这边先接真实会话能力。现在默认支持家庭账号登录；初始化阶段的
          Bootstrap 口令链路后面继续接。
        </p>
      </div>

      <form className="auth-screen__panel auth-screen__form" onSubmit={(event) => void handleSubmit(event)}>
        <label>
          用户名
          <input
            autoComplete="username"
            value={username}
            onChange={event => setUsername(event.target.value)}
            placeholder="请输入用户名"
          />
        </label>

        <label>
          密码
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={event => setPassword(event.target.value)}
            placeholder="请输入密码"
          />
        </label>

        {loginError ? <div className="auth-screen__error">{loginError}</div> : null}

        <button className="btn btn--primary auth-screen__submit" type="submit" disabled={loginPending || !username.trim() || !password}>
          {loginPending ? '登录中...' : '进入家庭空间'}
        </button>
      </form>
    </div>
  );
}
