import { z } from 'zod'
import { apiFetch } from '../api/client'
import {
  AccessRequestInputSchema,
  ChatReplySchema,
  ChecklistSchema,
  ContactListSchema,
  InternListSchema,
  KbListSchema,
  LeaveRequestInputSchema,
  MetricsSchema,
  RequestSchema,
  RequestListSchema,
  UserListSchema,
  UserSchema,
  PendingItemListSchema,
  type PendingItem,
  type AccessRequestInput,
  type ChatReply,
  type Checklist,
  type Contact,
  type InternSummary,
  type ItemStatus,
  type KbArticle,
  type LeaveRequestInput,
  type Metrics,
  type Request,
  type User,
} from '../api/schemas'

export interface AccessSystem {
  id: string
  name: string
  description: string
  defaultDurationDays: number
}

const AccessSystemListSchema = z.array(
  z.object({
    id: z.string(),
    name: z.string(),
    description: z.string(),
    defaultDurationDays: z.number(),
  }),
)

export interface BuddyService {
  getUsers(): Promise<User[]>
  getMe(): Promise<User>
  getChecklist(): Promise<Checklist>
  updateItemStatus(itemId: string, status: ItemStatus): Promise<Checklist>
  listRequests(scope?: 'queue'): Promise<Request[]>
  createLeaveRequest(input: LeaveRequestInput): Promise<Request>
  requestAccess(input: AccessRequestInput): Promise<Request>
  approveRequest(id: string): Promise<Request>
  rejectRequest(id: string, comment?: string): Promise<Request>
  sendRequest(id: string): Promise<Request>
  getContacts(): Promise<Contact[]>
  getKbArticles(): Promise<KbArticle[]>
  getAccessSystems(): Promise<AccessSystem[]>
  getMetrics(): Promise<Metrics>
  getInterns(): Promise<InternSummary[]>
  getPendingItems(): Promise<PendingItem[]>
  approveChecklistItem(itemId: string, userId: string): Promise<PendingItem[]>
  sendChatMessage(message: string): Promise<ChatReply>
}

export const service: BuddyService = {
  getUsers: () => apiFetch('/api/users', { schema: UserListSchema }),
  getMe: () => apiFetch('/api/me', { schema: UserSchema }),
  getChecklist: () => apiFetch('/api/checklist', { schema: ChecklistSchema }),
  updateItemStatus: (itemId, status) =>
    apiFetch(`/api/checklist/items/${itemId}/status`, {
      method: 'POST',
      body: { status },
      schema: ChecklistSchema,
    }),
  listRequests: (scope) =>
    apiFetch(scope ? `/api/requests?scope=queue` : '/api/requests', { schema: RequestListSchema }),
  createLeaveRequest: async (input) =>
    apiFetch('/api/requests/leave', {
      method: 'POST',
      body: LeaveRequestInputSchema.parse(input),
      schema: RequestSchema,
    }),
  requestAccess: async (input) =>
    apiFetch('/api/requests/access', {
      method: 'POST',
      body: AccessRequestInputSchema.parse(input),
      schema: RequestSchema,
    }),
  approveRequest: (id) =>
    apiFetch(`/api/requests/${id}/approve`, { method: 'POST', schema: RequestSchema }),
  rejectRequest: (id, comment) =>
    apiFetch(`/api/requests/${id}/reject`, { method: 'POST', body: { comment }, schema: RequestSchema }),
  sendRequest: (id) =>
    apiFetch(`/api/requests/${id}/send`, { method: 'POST', schema: RequestSchema }),
  getContacts: () => apiFetch('/api/contacts', { schema: ContactListSchema }),
  getKbArticles: () => apiFetch('/api/kb', { schema: KbListSchema }),
  getAccessSystems: () => apiFetch('/api/access-systems', { schema: AccessSystemListSchema }),
  getMetrics: () => apiFetch('/api/metrics', { schema: MetricsSchema }),
  getInterns: () => apiFetch('/api/interns', { schema: InternListSchema }),
  getPendingItems: () => apiFetch('/api/pending-items', { schema: PendingItemListSchema }),
  approveChecklistItem: (itemId, userId) =>
    apiFetch(`/api/checklist/items/${itemId}/approve`, {
      method: 'POST',
      body: { userId },
      schema: PendingItemListSchema,
    }),
  sendChatMessage: (message) =>
    apiFetch('/api/chat', { method: 'POST', body: { message }, schema: ChatReplySchema }),
}
