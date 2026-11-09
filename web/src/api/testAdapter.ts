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
import type { ApiClient, ConfirmResult, MessageReply, SessionInfo, Workspace } from './types';

export type DemoPhase = 'initial' | 'pending' | 'approved' | 'granted' | 'rejected';

const requestStatusLabels: Record<string, string> = {
  pending: 'на согласовании',
  approved: 'одобрена',
  rejected: 'отклонена',
};

export class TestApiClient implements ApiClient {
  private phase: DemoPhase = 'initial';
  private confirmResult: ConfirmResult | null = null;
  private userMessageCount = 0;
  private readonly latencyMs: number;

  constructor(latencyMs = 0) {
    this.latencyMs = latencyMs;
  }

  setDemoPhase(phase: DemoPhase): void {
    this.phase = phase;
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
    return this.confirmResult;
  }
}
