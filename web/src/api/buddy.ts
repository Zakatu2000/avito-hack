import { ApiError, NetworkError, SessionExpiredError } from './errors';
import { storeSession } from './client';

export type ChecklistStatus =
  | 'available'
  | 'in_progress'
  | 'evidence_pending'
  | 'completed'
  | 'blocked';

export type ChecklistTiming = 'overdue' | 'now' | 'next' | 'done';

export interface BuddyProfile {
  track: string;
  roleCode: string;
  grade: string;
  weekNo: number;
  startDate: string;
  mentorName: string;
  curatorName: string;
  unit: string;
  stage: string;
}

export interface BuddyProgress {
  total: number;
  completed: number;
  pct: number;
}

export interface NextStepRef {
  id?: string;
  itemId?: string;
  title: string;
  status: ChecklistStatus | string;
  timing?: ChecklistTiming | string;
  stageLabel: string;
  stage?: string;
  actor?: string;
}

export interface ChecklistItem {
  id: string;
  track: string;
  title: string;
  description: string;
  instructions: string[];
  stage: string;
  stageLabel: string;
  stageOrder: number;
  actor: string;
  status: ChecklistStatus;
  timing: ChecklistTiming;
  blockedBy: string[];
  evidence: string;
  objective: string;
  completionPolicy: string;
  evidenceUri: string | null;
  note: string;
  sourceRef: { sheet: string; row: number };
}

export interface BuddySource {
  chunkId: string;
  docId: string;
  title: string;
  section: string;
  url: string | null;
  tier: string;
  sourceType: string;
  sourceStatus: string;
  freshness: string;
  quote: string;
  conflictNote: string | null;
  snippet: string;
  topics: string[];
  checklistRefs: string[];
  score: number;
}

export interface ActionPreview {
  actionId: string;
  actionType: string;
  label: string;
  payload: Record<string, string>;
  idempotencyKey: string;
  confirmationToken: string;
  status: 'draft_preview' | 'executed' | 'cancelled' | 'failed' | string;
  checklistItemId: string | null;
  result: Record<string, unknown> | null;
  demo: boolean;
  createdAt: string;
}

export interface CuratorBreakdown {
  kind: 'curator_breakdown';
  decision: string;
  constraints: string[];
  openQuestions: string[];
  actionItems: string[];
}

export interface BuddyLearning {
  kind: string;
  topics?: string[];
  socratic?: boolean;
  decision?: string;
  constraints?: string[];
  openQuestions?: string[];
  actionItems?: string[];
}

export interface BuddyChatReply {
  intent: string;
  text: string;
  profile: BuddyProfile;
  progress: BuddyProgress;
  nextStep: NextStepRef | null;
  checklistItem: NextStepRef | null;
  sources: BuddySource[];
  learning: BuddyLearning | null;
  actionPreview: ActionPreview | null;
  abstained: boolean;
  handoff: boolean;
  mode: string;
  aiMode: string;
}

export interface GeminiImage {
  file: string;
  sha256: string;
  altText: string;
}

export interface BuddyBootstrap {
  profile: BuddyProfile;
  progress: BuddyProgress;
  nextSteps: NextStepRef[];
  checklistCount: number;
  aiMode: string;
  demoIntegrations: string;
  geminiImages: GeminiImage[];
}

export interface AuditEvent {
  id: number;
  actionId: string | null;
  event: string;
  payload: Record<string, unknown>;
  at: string;
}

export interface CompetencyAxis {
  id: string;
  label: string;
  ideal?: string;
}

export interface CompetencyPlanEntry {
  axisId: string;
  action: string;
  dueStage: string;
}

export interface CompetencyAssessment {
  id: string;
  track: string;
  ratings: Record<string, number>;
  priorities: string[];
  plan: CompetencyPlanEntry[];
  evidence: Record<string, unknown>;
  createdAt: string;
}

export interface CuratorMessage {
  id: number;
  direction: 'in' | 'out';
  channel: string;
  body: string;
  parsed: Record<string, unknown> | null;
  at: string;
}

export interface ConfirmActionResult extends ActionPreview {
  idempotentReplay: boolean;
}

export interface BuddyClient {
  bootstrap(): Promise<BuddyBootstrap>;
  getChecklist(): Promise<{
    items: ChecklistItem[];
    progress: BuddyProgress;
    profile: BuddyProfile;
  }>;
  transition(
    itemId: string,
    target: ChecklistStatus,
    options?: { evidenceUri?: string; note?: string },
  ): Promise<{ item: ChecklistItem; progress: BuddyProgress }>;
  chat(text: string): Promise<BuddyChatReply>;
  previewAction(
    actionType: string,
    payload: Record<string, string>,
    checklistItemId?: string,
  ): Promise<{ actionPreview: ActionPreview; duplicatePreview: boolean }>;
  confirmAction(
    actionId: string,
    confirmationToken: string,
    clientKey?: string,
  ): Promise<ConfirmActionResult>;
  cancelAction(actionId: string): Promise<{ cancelled: boolean; actionId: string }>;
  listActions(): Promise<{ actions: ActionPreview[] }>;
  audit(): Promise<{ events: AuditEvent[] }>;
  competencyAxes(): Promise<{
    axes: CompetencyAxis[];
    scale: { min: number; max: number };
    source: Record<string, unknown>;
  }>;
  competencyLatest(): Promise<{ assessment: CompetencyAssessment | null }>;
  saveCompetency(payload: {
    ratings: Record<string, number>;
    priorities: string[];
    plan: CompetencyPlanEntry[];
    evidence?: Record<string, unknown>;
  }): Promise<{ assessment: CompetencyAssessment }>;
  sendCompetency(
    assessmentId: string,
  ): Promise<{ actionPreview: ActionPreview; duplicatePreview: boolean }>;
  curatorHistory(): Promise<{ messages: CuratorMessage[] }>;
}

export class HttpBuddyClient implements BuddyClient {
  private readonly baseUrl: string;

  constructor(baseUrl = '/api/buddy') {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set('Accept', 'application/json');
    if (init.body !== undefined) headers.set('Content-Type', 'application/json');
    let response: Response;
    try {
      response = await window.fetch(`${this.baseUrl}${path}`, {
        ...init,
        headers,
        credentials: 'same-origin',
      });
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
        const data = await response.json();
        if (typeof data.message === 'string') message = data.message;
      } catch {
        /* Preserve HTTP failure even for a non-JSON body. */
      }
      throw new ApiError(response.status, message);
    }
    return response.json() as Promise<T>;
  }

  bootstrap(): Promise<BuddyBootstrap> {
    return this.request('/bootstrap');
  }

  getChecklist(): Promise<{
    items: ChecklistItem[];
    progress: BuddyProgress;
    profile: BuddyProfile;
  }> {
    return this.request('/checklist');
  }

  transition(
    itemId: string,
    target: ChecklistStatus,
    options: { evidenceUri?: string; note?: string } = {},
  ): Promise<{ item: ChecklistItem; progress: BuddyProgress }> {
    return this.request(`/checklist/${encodeURIComponent(itemId)}/transition`, {
      method: 'POST',
      body: JSON.stringify({ target, ...options }),
    });
  }

  chat(text: string): Promise<BuddyChatReply> {
    return this.request('/chat', { method: 'POST', body: JSON.stringify({ text }) });
  }

  previewAction(
    actionType: string,
    payload: Record<string, string>,
    checklistItemId?: string,
  ): Promise<{ actionPreview: ActionPreview; duplicatePreview: boolean }> {
    return this.request('/actions/preview', {
      method: 'POST',
      body: JSON.stringify({ actionType, payload, checklistItemId }),
    });
  }

  confirmAction(
    actionId: string,
    confirmationToken: string,
    clientKey?: string,
  ): Promise<ConfirmActionResult> {
    const headers = new Headers();
    if (clientKey !== undefined) headers.set('Idempotency-Key', clientKey);
    return this.request(`/actions/${encodeURIComponent(actionId)}/confirm`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ confirmationToken }),
    });
  }

  cancelAction(actionId: string): Promise<{ cancelled: boolean; actionId: string }> {
    return this.request(`/actions/${encodeURIComponent(actionId)}/cancel`, {
      method: 'POST',
    });
  }

  listActions(): Promise<{ actions: ActionPreview[] }> {
    return this.request('/actions');
  }

  audit(): Promise<{ events: AuditEvent[] }> {
    return this.request('/audit');
  }

  competencyAxes(): Promise<{
    axes: CompetencyAxis[];
    scale: { min: number; max: number };
    source: Record<string, unknown>;
  }> {
    return this.request('/competency/axes');
  }

  competencyLatest(): Promise<{ assessment: CompetencyAssessment | null }> {
    return this.request('/competency/latest');
  }

  saveCompetency(payload: {
    ratings: Record<string, number>;
    priorities: string[];
    plan: CompetencyPlanEntry[];
    evidence?: Record<string, unknown>;
  }): Promise<{ assessment: CompetencyAssessment }> {
    return this.request('/competency', { method: 'POST', body: JSON.stringify(payload) });
  }

  sendCompetency(
    assessmentId: string,
  ): Promise<{ actionPreview: ActionPreview; duplicatePreview: boolean }> {
    return this.request(`/competency/${encodeURIComponent(assessmentId)}/send`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
  }

  curatorHistory(): Promise<{ messages: CuratorMessage[] }> {
    return this.request('/curator/history');
  }
}

export function createBuddyClient(): BuddyClient {
  const base = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/+$/, '');
  return new HttpBuddyClient(`${base}/buddy`);
}
