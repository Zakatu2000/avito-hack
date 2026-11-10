import { useState } from 'react';
import type { ApiClient, SessionInfo } from '../api/types';
import { HttpApiClient } from '../api/client';
import { exampleSessions } from '../api/fixtures';

const roleLabels: Record<string, string> = {
  trainee: 'стажёр',
  operator: 'демооператор',
};

interface LoginScreenProps {
  client: ApiClient;
  onLogin: (session: SessionInfo) => void;
  expired: boolean;
}

export function LoginScreen({ client, onLogin, expired }: LoginScreenProps) {
  const [pendingLogin, setPendingLogin] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function signIn(login: string) {
    setError(null);
    setPendingLogin(login);
    try {
      const session = await client.login(login);
      onLogin(session);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось войти');
    } finally {
      setPendingLogin(null);
    }
  }

  const sessions = client instanceof HttpApiClient
    ? ['intern-demo', 'intern-ready', 'intern-new', 'operator-demo'].map((login) => ({
        user: { login, displayName: login, role: login === 'operator-demo' ? 'operator' : 'trainee' },
      })) : exampleSessions;

  return (
    <main className="login-wrap">
      <section className="card login-card" aria-labelledby="login-title">
        <h1 id="login-title">AI-buddy · «Первый PR»</h1>
        <p className="muted">
          Тестовый вход в синтетической сессии. Права проверяет сервер, роль из браузера не передаётся.
        </p>
        {expired && (
          <div className="notice notice-warn" role="status" data-testid="expired-note">
            Тестовая сессия истекла. Войдите заново.
          </div>
        )}
        <div className="btn-col">
          {sessions.map((session) => (
            <button
              key={session.user.login}
              className="btn btn-primary"
              disabled={pendingLogin !== null}
              onClick={() => void signIn(session.user.login)}
            >
              {pendingLogin === session.user.login
                ? 'Входим…'
                : `Войти как ${session.user.displayName} (${roleLabels[session.user.role]})`}
            </button>
          ))}
        </div>
        {error && (
          <div className="notice notice-err" role="alert">
            {error}
          </div>
        )}
      </section>
    </main>
  );
}
