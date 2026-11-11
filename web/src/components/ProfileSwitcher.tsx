import { useState } from 'react';
import type { ApiClient, SessionInfo } from '../api/types';

const profiles = [
  { login: 'intern-demo', label: 'Backend · intern-demo' },
  { login: 'intern-ready', label: 'Backend · intern-ready' },
  { login: 'intern-new', label: 'Backend · intern-new' },
  { login: 'intern-analytics', label: 'Аналитика · intern-analytics' },
  { login: 'intern-marketing', label: 'Маркетинг · intern-marketing' },
];

interface ProfileSwitcherProps {
  client: ApiClient;
  currentLogin: string;
  onChanged: (session: SessionInfo) => void;
}

export function ProfileSwitcher({ client, currentLogin, onChanged }: ProfileSwitcherProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function switchProfile(login: string) {
    if (login === currentLogin || pending) return;
    setPending(true);
    setError(null);
    try {
      onChanged(await client.login(login));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось сменить профиль');
    } finally {
      setPending(false);
    }
  }

  return (
    <label className="profile-switcher">
      <span className="sr-only">Демо-профиль</span>
      <select aria-label="Демо-профиль" value={currentLogin}
        disabled={pending} onChange={(event) => void switchProfile(event.target.value)}>
        {profiles.map((profile) => <option key={profile.login} value={profile.login}>{profile.label}</option>)}
      </select>
      {pending && <span className="small">Переключаем…</span>}
      {error && <span className="small" role="alert">{error}</span>}
    </label>
  );
}
