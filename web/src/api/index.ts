import { HttpApiClient } from './client';
import { TestApiClient } from './testAdapter';
import type { ApiClient } from './types';

export function createClient(): ApiClient {
  const mode = import.meta.env.VITE_API_MODE ?? 'test';
  if (mode === 'http') {
    return new HttpApiClient(import.meta.env.VITE_API_BASE_URL ?? '/api');
  }
  const params = new URLSearchParams(window.location.search);
  const parsed = Number(params.get('latency') ?? '0');
  const latency = Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
  return new TestApiClient(latency);
}

export { HttpApiClient, readStoredSession, storeSession } from './client';
export { TestApiClient } from './testAdapter';
export * from './fixtures';
export * from './types';
export { ApiError, NetworkError, SessionExpiredError } from './errors';
