import { useCallback, useEffect, useState } from 'react';
import { SessionExpiredError } from '../api/errors';
import type { ApiClient, Workspace } from '../api/types';

type ScreenState =
  | { phase: 'loading' }
  | { phase: 'ready'; workspace: Workspace }
  | { phase: 'error'; message: string }
  | { phase: 'expired' };

export function useWorkspace(client: ApiClient, onExpired: () => void) {
  const [state, setState] = useState<ScreenState>({ phase: 'loading' });

  const load = useCallback(async () => {
    setState({ phase: 'loading' });
    try {
      const workspace = await client.getWorkspace();
      setState({ phase: 'ready', workspace });
    } catch (error) {
      if (error instanceof SessionExpiredError) {
        setState({ phase: 'expired' });
        onExpired();
        return;
      }
      const message = error instanceof Error ? error.message : 'Неизвестная ошибка';
      setState({ phase: 'error', message });
    }
  }, [client, onExpired]);

  useEffect(() => {
    void load();
  }, [load]);

  return { state, refresh: load };
}
