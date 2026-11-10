export type AiMode = 'real' | 'demo';
export type AccessState = 'granted' | 'denied' | 'unknown';
export type RequestStatus = 'pending' | 'approved' | 'rejected';
export type MessageResultType = 'text' | 'clarification' | 'proposal' | 'request-status';

export interface SessionUser {
  id: string;
  login: string;
  displayName: string;
  role: 'trainee' | 'operator';
}

export interface SessionInfo {
  token: string;
  user: SessionUser;
}

export interface TaskInstruction {
  title: string;
  url: string;
}

export interface WorkspaceTask {
  id: string;
  title: string;
  summary: string;
  resourceId: string;
  resourceName: string;
  instruction: TaskInstruction | null;
}

export interface ServiceRequest {
  id: string;
  status: RequestStatus;
  resource: string;
  purpose: string;
}

export interface NextStep {
  code: string;
  title: string;
  items: string[];
}

export interface Workspace {
  user: SessionUser;
  task: WorkspaceTask | null;
  effectiveAccess: AccessState;
  request: ServiceRequest | null;
  nextStep: NextStep | null;
  aiMode: AiMode;
}

export interface Proposal {
  id: string;
  resource: string;
  purpose: string;
  action: string;
  idempotencyKey: string;
}

export interface MessageReply {
  type: MessageResultType;
  text: string;
  source: string | null;
  proposal: Proposal | null;
  request: ServiceRequest | null;
  nextStep: NextStep | null;
  aiMode: AiMode;
}

export interface ConfirmResult {
  request: ServiceRequest;
  nextStep: NextStep | null;
}

export interface TaskReturnEvent {
  name: 'task_returned';
  taskId: string;
  requestId: string | null;
}

export interface ApiClient {
  login(login: string): Promise<SessionInfo>;
  logout(): Promise<void>;
  getWorkspace(): Promise<Workspace>;
  sendMessage(text: string): Promise<MessageReply>;
  confirmProposal(proposalId: string, idempotencyKey: string): Promise<ConfirmResult>;
  reportTaskReturn(taskId: string, requestId: string | null): Promise<void>;
}
