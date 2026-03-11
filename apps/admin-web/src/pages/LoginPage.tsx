import { useState, type FormEvent } from "react";

import { useAuth } from "../state/auth";

export function LoginPage() {
  const { login, loginPending, loginError } = useAuth();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await login(username.trim(), password);
    } catch {
      return;
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-panel">
        <div className="auth-copy">
          <span className="auth-kicker">FamilyClaw Admin</span>
          <h1>管理台登录</h1>
          <p>现在后端只认真实会话，不再认前端硬塞的管理员头。用管理员账号密码登录。</p>
        </div>

        <form className="auth-form" onSubmit={(event) => void handleSubmit(event)}>
          <label>
            管理员账号
            <input
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="请输入账号"
            />
          </label>

          <label>
            密码
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="请输入密码"
            />
          </label>

          {loginError ? <div className="auth-error">{loginError}</div> : null}

          <button type="submit" disabled={loginPending || !username.trim() || !password}>
            {loginPending ? "登录中..." : "进入管理台"}
          </button>
        </form>
      </div>
    </div>
  );
}
