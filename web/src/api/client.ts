import { ApiError, NetworkError, SessionExpiredError } from './errors';
import type { ApiClient, ConfirmResult, MessageReply, SessionInfo, Workspace } from './types';

const TOKEN_KEY = 'aibuddy.session';

function isValidSession(value: unknown): value is SessionInfo {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return typeof v.token === 'string'
    && typeof v.user === 'object' && v.user !== null
    && typeof (v.user as Record<string, unknown>).login === 'string'
    && typeof (v.user as Record<string, unknown>).role === 'string';
}

export function readStoredSession(): SessionInfo | null {
  try {
    const raw = window.localStorage.getItem(TOKEN_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return isValidSession(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function storeSession(session: SessionInfo | null): void {
  try {
    if (session === null) {
      window.localStorage.removeItem(TOKEN_KEY);
    } else {
      window.localStorage.setItem(TOKEN_KEY, JSON.stringify(session));
    }
  } catch {
    return;
  }
}

export class HttpApiClient implements ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl = '/api') {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const session = readStoredSession();
    const headers = new Headers(init.headers);
    headers.set('Accept', 'application/json');
    if (session) headers.set('Authorization', `Bearer ${session.token}`);
    if (init.body !== undefined) headers.set('Content-Type', 'application/json');

    let response: Response;
    try {
      response = await window.fetch(`${this.baseUrl}${path}`, { ...init, headers });
    } catch {
      throw new NetworkError();
    }

    if (response.status === 401) {
      storeSession(null);
      throw new SessionExpiredError();
    }
    if (!response.ok) {
      let message = `Ошибка сервера (${response.status})`;
      try {
        const data: unknown = await response.json();
        if (typeof data === 'object' && data !== null && typeof (data as Record<string, unknown>).message === 'string') {
          message = (data as Record<string, string>).message;
        }
      } catch {
        throw new ApiError(response.status, message);
      }
      throw new ApiError(response.status, message);
    }
    return (await response.json()) as T;
  }

  async login(login: string): Promise<SessionInfo> {
    const session = await this.request<SessionInfo>('/session', {
      method: 'POST',
      body: JSON.stringify({ login }),
    });
    storeSession(session);
    return session;
  }

  async logout(): Promise<void> {
    try {
      await this.request('/session', { method: 'DELETE' });
    } finally {
      storeSession(null);
    }
  }

  getWorkspace(): Promise<Workspace> {
    return this.request<Workspace>('/workspace');
  }

  sendMessage(text: string): Promise<MessageReply> {
    return this.request<MessageReply>('/messages', {
      method: 'POST',
      body: JSON.stringify({ text }),
    });
  }

  confirmProposal(proposalId: string, idempotencyKey: string): Promise<ConfirmResult> {
    return this.request<ConfirmResult>(`/proposals/${encodeURIComponent(proposalId)}/confirm`, {
      method: 'POST',
      body: JSON.stringify({ idempotencyKey }),
    });
  }
}
