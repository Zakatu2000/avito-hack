import { useCallback, useState } from 'react';
import { createClient } from './api';
import { readStoredSession, storeSession } from './api/client';
import type { ApiClient, SessionInfo } from './api/types';
import { LoginScreen } from './components/LoginScreen';
import { WorkspaceScreen } from './components/WorkspaceScreen';

export interface AppProps {
  client?: ApiClient;
}

export function App({ client: clientProp }: AppProps) {
  const [defaultClient] = useState<ApiClient>(createClient);
  const client = clientProp ?? defaultClient;
  const [session, setSession] = useState<SessionInfo | null>(() => readStoredSession());
  const [expired, setExpired] = useState(false);

  const handleLogin = useCallback((loggedIn: SessionInfo) => {
    setExpired(false);
    setSession(loggedIn);
  }, []);

  const handleLogout = useCallback(() => {
    storeSession(null);
    setSession(null);
    setExpired(false);
  }, []);

  const handleExpired = useCallback(() => {
    storeSession(null);
    setSession(null);
    setExpired(true);
  }, []);

  if (session === null) {
    return <LoginScreen client={client} onLogin={handleLogin} expired={expired} />;
  }
  return <WorkspaceScreen client={client} session={session} onExpired={handleExpired} onLogout={handleLogout} />;
}
