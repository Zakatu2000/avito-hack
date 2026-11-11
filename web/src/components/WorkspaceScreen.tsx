import { useState } from 'react';
import { useWorkspace } from '../hooks/useWorkspace';
import { WorkspaceBody } from './WorkspaceBody';
import type { ApiClient, SessionInfo } from '../api/types';
import { HttpApiClient } from '../api/client';
import { createBuddyClient } from '../api/buddy';
import { BuddyPanel } from './BuddyPanel';
import { ProfileSwitcher } from './ProfileSwitcher';

interface WorkspaceScreenProps {
  client: ApiClient;
  session: SessionInfo;
  onSessionChange: (session: SessionInfo) => void;
  onExpired: () => void;
  onLogout: () => void;
}

export function WorkspaceScreen({ client, session, onSessionChange, onExpired, onLogout }: WorkspaceScreenProps) {
  const { state, refreshing, refresh } = useWorkspace(client, onExpired);
  const [activeTab, setActiveTab] = useState<'task' | 'onboarding'>('onboarding');
  const [buddyClient] = useState(createBuddyClient);
  const showBuddy = client instanceof HttpApiClient && session.user.role === 'trainee';

  async function signOut() {
    try {
      await client.logout();
    } finally {
      onLogout();
    }
  }

  const workspace = state.phase === 'ready' ? state.workspace : null;
  const aiMode = workspace !== null ? workspace.aiMode : 'demo';

  return (
    <div className="app-shell">
      <header className="topbar">
        <span className="brand">AI-buddy · «Первый PR»</span>
        <span className={`aimode aimode-${aiMode}`} data-testid="aimode-badge">
          Режим AI: {aiMode === 'real' ? 'реальный' : 'демо'}
        </span>
        {showBuddy && <span className="mock-badge" data-testid="mock-integrations">Интеграции: mock</span>}
        {showBuddy && <ProfileSwitcher client={client} currentLogin={session.user.login} onChanged={onSessionChange} />}
        <span className="topbar-user muted">{session.user.displayName}</span>
        <button className="btn btn-ghost" onClick={() => void signOut()}>
          Выйти
        </button>
      </header>

      <main className="workspace">
        {state.phase === 'loading' && (
          <section className="card" aria-busy="true" data-testid="loading-state">
            <div className="card-label">Рабочее пространство</div>
            <p role="status">Загружаем рабочее пространство…</p>
            <div className="skeleton" />
            <div className="skeleton skeleton-short" />
          </section>
        )}

        {state.phase === 'error' && (
          <section className="card" data-testid="error-state">
            <div className="notice notice-err" role="alert">
              {state.message}
            </div>
            <p className="muted">Показываем экран ошибки. Серверное состояние не меняем.</p>
            <button className="btn btn-primary" onClick={() => void refresh()}>
              Повторить
            </button>
          </section>
        )}

        {state.phase === 'expired' && (
          <section className="card" data-testid="expired-state">
            <div className="notice notice-warn" role="status">
              Тестовая сессия истекла. Войдите заново.
            </div>
          </section>
        )}

        {workspace !== null && (
          <>
            {showBuddy && <nav className="workspace-tabs" aria-label="Разделы рабочего пространства">
              <button className={`tab-btn ${activeTab === 'task' ? 'tab-active' : ''}`} aria-pressed={activeTab === 'task'}
                onClick={() => setActiveTab('task')}>Задача</button>
              <button className={`tab-btn ${activeTab === 'onboarding' ? 'tab-active' : ''}`} aria-pressed={activeTab === 'onboarding'}
                onClick={() => setActiveTab('onboarding')}>Онбординг</button>
            </nav>}
            {showBuddy && activeTab === 'onboarding'
              ? <BuddyPanel client={buddyClient} onExpired={onExpired} />
              : <WorkspaceBody workspace={workspace} client={client} onRefresh={() => void refresh()} refreshing={refreshing} />}
          </>
        )}
      </main>
    </div>
  );
}
