import { useCallback, useEffect, useRef, useState } from 'react';
import { SessionExpiredError } from '../api/errors';
import type { ApiClient, Workspace } from '../api/types';

type ScreenState =
  | { phase: 'loading' }
  | { phase: 'ready'; workspace: Workspace }
  | { phase: 'error'; message: string }
  | { phase: 'expired' };

export function useWorkspace(client: ApiClient, onExpired: () => void) {
  const [state, setState] = useState<ScreenState>({ phase: 'loading' });
  const [refreshing, setRefreshing] = useState(false);
  const hasDataRef = useRef(false);

  const load = useCallback(async () => {
    if (!hasDataRef.current) setState({ phase: 'loading' });
    setRefreshing(true);
    try {
      const workspace = await client.getWorkspace();
      hasDataRef.current = true;
      setState({ phase: 'ready', workspace });
    } catch (error) {
      if (error instanceof SessionExpiredError) {
        hasDataRef.current = false;
        setState({ phase: 'expired' });
        onExpired();
        return;
      }
      const message = error instanceof Error ? error.message : 'Неизвестная ошибка';
      if (!hasDataRef.current) {
        setState({ phase: 'error', message });
      }
    } finally {
      setRefreshing(false);
    }
  }, [client, onExpired]);

  useEffect(() => {
    void load();
  }, [load]);

  return { state, refreshing, refresh: load };
}
