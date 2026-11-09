import { HttpApiClient } from './client';
import { TestApiClient } from './testAdapter';
import type { ApiClient } from './types';

export function createClient(): ApiClient {
  const mode = import.meta.env.VITE_API_MODE ?? 'test';
  if (mode === 'http') {
    return new HttpApiClient(import.meta.env.VITE_API_BASE_URL ?? '/api');
  }
  return new TestApiClient();
}

export { HttpApiClient, readStoredSession, storeSession } from './client';
export { TestApiClient } from './testAdapter';
export * from './fixtures';
export * from './types';
export { ApiError, NetworkError, SessionExpiredError } from './errors';
