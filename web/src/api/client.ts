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

interface WireWorkspace {
  task: { taskId: string; title: string; resourceId: string } | null;
  source: { sourceId: string; excerpt: string } | null;
  effectiveAccess: 'missing' | 'granted' | 'unknown';
  request: { requestId: string; requestStatus: 'pending' | 'approved' | 'rejected' } | null;
  nextStep: string;
}
interface WireReply {
  text: string; aiMode: 'demo' | 'live'; source: WireWorkspace['source'];
  proposal: { proposalId: string; resourceId: string; summary: string } | null;
  workspace: WireWorkspace;
}
interface Identity {
  user: SessionInfo['user']; aiMode: 'demo' | 'live'; demoOperator: boolean;
}

export class HttpApiClient implements ApiClient {
  private readonly baseUrl: string;
  private identity: Identity | null = null;

  constructor(baseUrl = '/api') { this.baseUrl = baseUrl.replace(/\/+$/, ''); }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set('Accept', 'application/json');
    if (init.body !== undefined) headers.set('Content-Type', 'application/json');
    let response: Response;
    try {
      response = await window.fetch(`${this.baseUrl}${path}`, { ...init, headers, credentials: 'same-origin' });
    } catch { throw new NetworkError(); }
    if (response.status === 401) { storeSession(null); throw new SessionExpiredError(); }
    if (!response.ok) {
      let message = `Ошибка сервера (${response.status})`;
      try { const data = await response.json(); if (typeof data.message === 'string') message = data.message; }
      catch { /* Preserve HTTP failure even for a non-JSON body. */ }
      throw new ApiError(response.status, message);
    }
    return response.json() as Promise<T>;
  }

  private convert(w: WireWorkspace, identity: Identity): Workspace {
    return {
      user: identity.user,
      task: w.task ? { id: w.task.taskId, title: w.task.title, resourceId: w.task.resourceId,
        resourceName: w.task.resourceId, summary: w.source?.excerpt ?? 'Учебная задача', instruction: null } : null,
      effectiveAccess: w.effectiveAccess === 'missing' ? 'denied' : w.effectiveAccess,
      request: w.request ? { id: w.request.requestId, status: w.request.requestStatus,
        resource: w.task?.resourceId ?? '', purpose: w.task?.title ?? '' } : null,
      nextStep: { code: w.effectiveAccess === 'granted' ? 'return-to-task' : 'wait',
        title: w.nextStep, items: [] },
      aiMode: identity.aiMode === 'live' ? 'real' : 'demo',
    };
  }

  async login(login: string): Promise<SessionInfo> {
    await this.request<WireWorkspace>('/session', {
      method: 'POST', body: JSON.stringify({ username: login, password: 'training-only' }),
    });
    this.identity = await this.request<Identity>('/session');
    // Local storage keeps presentation metadata. Authentication uses HttpOnly cookie.
    const session = { token: '', user: this.identity.user };
    storeSession(session);
    return session;
  }

  async logout(): Promise<void> {
    try { await this.request('/session', { method: 'DELETE' }); }
    finally { this.identity = null; storeSession(null); }
  }

  async getWorkspace(): Promise<Workspace> {
    this.identity = await this.request<Identity>('/session');
    return this.convert(await this.request<WireWorkspace>('/workspace'), this.identity);
  }

  async sendMessage(text: string): Promise<MessageReply> {
    const identity = await this.request<Identity>('/session');
    const reply = await this.request<WireReply>('/messages', { method: 'POST', body: JSON.stringify({ text }) });
    const workspace = this.convert(reply.workspace, { ...identity, aiMode: reply.aiMode });
    return {
      type: reply.proposal ? 'proposal' : workspace.request ? 'request-status' : 'text',
      text: reply.text, source: reply.source?.excerpt ?? null,
      proposal: reply.proposal ? { id: reply.proposal.proposalId, resource: reply.proposal.resourceId,
        purpose: reply.proposal.summary, action: reply.proposal.summary,
        idempotencyKey: crypto.randomUUID() } : null,
      request: workspace.request, nextStep: workspace.nextStep, aiMode: workspace.aiMode,
    };
  }

  async confirmProposal(id: string, key: string): Promise<ConfirmResult> {
    const identity = await this.request<Identity>('/session');
    const wire = await this.request<WireWorkspace>(`/proposals/${encodeURIComponent(id)}/confirm`,
      { method: 'POST', headers: { 'Idempotency-Key': key } });
    const workspace = this.convert(wire, identity);
    if (!workspace.request) throw new ApiError(502, 'Сервис не вернул заявку');
    return { request: workspace.request, nextStep: workspace.nextStep };
  }

  async reportTaskReturn(taskId: string, requestId: string | null): Promise<void> {
    await this.request('/events', { method: 'POST',
      body: JSON.stringify({ name: 'task_link_opened', taskId, requestId }) });
  }
}
