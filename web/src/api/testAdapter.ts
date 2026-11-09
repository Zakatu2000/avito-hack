import { readStoredSession, storeSession } from './client';
import { ApiError, SessionExpiredError } from './errors';
import {
  exampleProposal,
  exampleRequestPending,
  exampleSessions,
  exampleWorkspaceApprovedNoAccess,
  exampleWorkspaceGranted,
  exampleWorkspaceInitial,
  exampleWorkspaceOperator,
  exampleWorkspacePending,
  exampleWorkspaceRejected,
} from './fixtures';
import type { ApiClient, ConfirmResult, MessageReply, SessionInfo, TaskReturnEvent, Workspace } from './types';

export type DemoPhase = 'initial' | 'pending' | 'approved' | 'granted' | 'rejected';

const requestStatusLabels: Record<string, string> = {
  pending: 'на согласовании',
  approved: 'одобрена',
  rejected: 'отклонена',
};

const DEMO_STATE_KEY = 'aibuddy.teststate';

interface PersistedDemoState {
  phase: DemoPhase;
  confirmResult: ConfirmResult | null;
}

function isValidPhase(value: unknown): value is DemoPhase {
  return typeof value === 'string' && ['initial', 'pending', 'approved', 'granted', 'rejected'].includes(value);
}

function readDemoState(): PersistedDemoState {
  try {
    const raw = window.localStorage.getItem(DEMO_STATE_KEY);
    if (!raw) return { phase: 'initial', confirmResult: null };
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null) return { phase: 'initial', confirmResult: null };
    const v = parsed as Record<string, unknown>;
    if (!isValidPhase(v.phase)) return { phase: 'initial', confirmResult: null };
    return { phase: v.phase, confirmResult: (v.confirmResult as ConfirmResult | null) ?? null };
  } catch {
    return { phase: 'initial', confirmResult: null };
  }
}

export class TestApiClient implements ApiClient {
  private phase: DemoPhase;
  private confirmResult: ConfirmResult | null;
  private userMessageCount = 0;
  private readonly latencyMs: number;
  private readonly events: TaskReturnEvent[] = [];

  constructor(latencyMs = 0) {
    this.latencyMs = latencyMs;
    const persisted = readDemoState();
    this.phase = persisted.phase;
    this.confirmResult = persisted.confirmResult;
  }

  recordedEvents(): readonly TaskReturnEvent[] {
    return this.events;
  }

  setDemoPhase(phase: DemoPhase): void {
    this.phase = phase;
    if (phase !== 'pending' && this.confirmResult !== null) {
      this.confirmResult = { ...this.confirmResult, request: { ...this.confirmResult.request, status: phase === 'rejected' ? 'rejected' : phase === 'approved' || phase === 'granted' ? 'approved' : 'pending' } };
    }
    this.persist();
  }

  resetDemo(): void {
    this.phase = 'initial';
    this.confirmResult = null;
    this.userMessageCount = 0;
    window.localStorage.removeItem(DEMO_STATE_KEY);
  }

  private persist(): void {
    try {
      const state: PersistedDemoState = { phase: this.phase, confirmResult: this.confirmResult };
      window.localStorage.setItem(DEMO_STATE_KEY, JSON.stringify(state));
    } catch {
      return;
    }
  }

  private delay(): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, this.latencyMs));
  }

  private workspaceForPhase(): Workspace {
    switch (this.phase) {
      case 'pending':
        return exampleWorkspacePending;
      case 'approved':
        return exampleWorkspaceApprovedNoAccess;
      case 'granted':
        return exampleWorkspaceGranted;
      case 'rejected':
        return exampleWorkspaceRejected;
      default:
        return exampleWorkspaceInitial;
    }
  }

  private requireSession(): SessionInfo {
    const session = readStoredSession();
    if (!session) throw new SessionExpiredError();
    return session;
  }

  async login(login: string): Promise<SessionInfo> {
    await this.delay();
    const found = exampleSessions.find((s) => s.user.login === login);
    if (!found) throw new ApiError(403, 'Неизвестная тестовая учётная запись');
    storeSession(found);
    return found;
  }

  async logout(): Promise<void> {
    storeSession(null);
  }

  async getWorkspace(): Promise<Workspace> {
    await this.delay();
    const session = this.requireSession();
    if (session.user.role === 'operator') return exampleWorkspaceOperator;
    return this.workspaceForPhase();
  }

  async sendMessage(_text: string): Promise<MessageReply> {
    await this.delay();
    this.requireSession();
    this.userMessageCount += 1;
    const workspace = this.workspaceForPhase();

    if (workspace.task === null) {
      return {
        type: 'text',
        text: 'Задача пока не назначена. Попросите руководителя назначить первую задачу.',
        source: 'workspace.task',
        proposal: null,
        request: null,
        nextStep: null,
        aiMode: workspace.aiMode,
      };
    }
    if (workspace.effectiveAccess === 'granted') {
      return {
        type: 'text',
        text: 'Доступ уже подтверждён сервером — возвращайтесь к задаче.',
        source: 'workspace.effectiveAccess',
        proposal: null,
        request: workspace.request,
        nextStep: workspace.nextStep,
        aiMode: workspace.aiMode,
      };
    }
    if (workspace.request !== null) {
      const label = requestStatusLabels[workspace.request.status] ?? workspace.request.status;
      return {
        type: 'request-status',
        text: `Заявка ${workspace.request.id} — ${label}. Новая заявка не нужна.`,
        source: 'workspace.request',
        proposal: null,
        request: workspace.request,
        nextStep: workspace.nextStep,
        aiMode: workspace.aiMode,
      };
    }
    if (this.userMessageCount === 1) {
      return {
        type: 'clarification',
        text: `Уточню, чтобы помочь точно: вы не можете открыть репозиторий задачи #${workspace.task.id} или речь о другом сервисе?`,
        source: 'workspace.task',
        proposal: null,
        request: null,
        nextStep: null,
        aiMode: workspace.aiMode,
      };
    }
    return {
      type: 'proposal',
      text: 'Проверил: задача назначена вам, права на репозиторий нет. Могу создать заявку на доступ — она оформится только после вашего подтверждения.',
      source: 'проверка назначения и права сервером',
      proposal: exampleProposal,
      request: null,
      nextStep: null,
      aiMode: workspace.aiMode,
    };
  }

  async confirmProposal(proposalId: string, idempotencyKey: string): Promise<ConfirmResult> {
    void idempotencyKey;
    await this.delay();
    this.requireSession();
    if (proposalId !== exampleProposal.id) {
      throw new ApiError(404, 'Предложение не найдено или устарело');
    }
    if (this.confirmResult !== null) return this.confirmResult;
    this.phase = 'pending';
    this.confirmResult = { request: exampleRequestPending, nextStep: null };
    this.persist();
    return this.confirmResult;
  }

  async reportTaskReturn(taskId: string, requestId: string | null): Promise<void> {
    await this.delay();
    this.requireSession();
    this.events.push({ name: 'task_returned', taskId, requestId });
  }
}
