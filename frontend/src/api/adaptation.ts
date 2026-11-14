import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { useAuthStore } from '../stores/auth'
import { isMockMode } from './auth'
import { apiFetch } from './client'
import {
  AdaptationMetricsSchema, AdaptationPlanSchema, ChatConfigSchema, ChatReplySchema,
  KnowledgeHitSchema, OpenFirstTaskSchema, RequestSchema,
  type NewRequestKind, type RequestOperation,
} from './schemas'

const Ok = z.object({ ok: z.boolean() })

export function useAdaptationPlan() {
  const userId = useAuthStore((state) => state.userId)
  return useQuery({
    queryKey: ['adaptation', 'plan', userId],
    enabled: !isMockMode && !!userId,
    queryFn: () => apiFetch('/api/adaptation/plan', { schema: AdaptationPlanSchema }),
  })
}

export function useAdaptationMetrics() {
  const userId = useAuthStore((state) => state.userId)
  return useQuery({
    queryKey: ['adaptation', 'metrics', userId],
    enabled: !isMockMode && !!userId,
    queryFn: () => apiFetch('/api/adaptation/metrics', { schema: AdaptationMetricsSchema }),
  })
}

export function useKnowledgeSearch(query: string, category = '', track = '', taskId = '') {
  const userId = useAuthStore((state) => state.userId)
  const params = new URLSearchParams({ q: query })
  if (category) params.set('category', category)
  if (track) params.set('track', track)
  if (taskId) params.set('taskId', taskId)
  return useQuery({
    queryKey: ['kb-search', userId, query, category, track, taskId],
    enabled: !isMockMode && !!userId && query.trim().length > 0,
    queryFn: () => apiFetch('/api/kb/search?' + params, { schema: z.array(KnowledgeHitSchema) }),
  })
}

function useRefreshPortal() {
  const cache = useQueryClient()
  return () => {
    for (const key of ['adaptation', 'requests', 'interns', 'pending-items', 'checklist']) {
      void cache.invalidateQueries({ queryKey: [key] })
    }
  }
}

export function useCreatePortalRequest() {
  const refresh = useRefreshPortal()
  return useMutation({
    mutationFn: ({ kind, body, key }: { kind: NewRequestKind; body: Record<string, unknown>; key: string }) =>
      apiFetch('/api/requests/' + kind, { method: 'POST', body, idempotencyKey: key, schema: RequestSchema }),
    onSettled: refresh,
  })
}

export function usePortalRequestAction() {
  const refresh = useRefreshPortal()
  return useMutation({
    mutationFn: ({ id, operation, body, version }: { id: string; operation: RequestOperation; body?: Record<string, unknown>; version?: string }) =>
      apiFetch('/api/requests/' + encodeURIComponent(id) + '/' + operation, { method: 'POST', body, requestVersion: version, schema: RequestSchema }),
    onSettled: refresh,
  })
}

export function useFirstTask() {
  const refresh = useRefreshPortal()
  return useMutation({
    mutationFn: ({ operation, userId }: { operation: 'open' | 'start' | 'assign' | 'confirm'; userId?: string }) =>
      apiFetch('/api/adaptation/first-task/' + operation, {
        method: 'POST', body: userId ? { userId } : undefined, schema: OpenFirstTaskSchema.or(Ok),
      }),
    onSettled: refresh,
  })
}

export function useCatalogTransition() {
  const refresh = useRefreshPortal()
  return useMutation({
    mutationFn: ({ id, target, evidenceUri }: { id: string; target: string; evidenceUri?: string }) =>
      apiFetch('/api/adaptation/items/' + encodeURIComponent(id) + '/transition', {
        method: 'POST', body: { target, evidenceUri }, schema: AdaptationPlanSchema,
      }),
    onSettled: refresh,
  })
}

export function useChatConfig() {
  const userId = useAuthStore((state) => state.userId)
  return useQuery({
    queryKey: ['chat-config', userId], enabled: !isMockMode && !!userId,
    queryFn: () => apiFetch('/api/chat/config', { schema: ChatConfigSchema }),
  })
}

export function usePortalChat() {
  return useMutation({
    mutationFn: ({ message, messageId, taskId }: { message: string; messageId: string; taskId?: string }) =>
      apiFetch('/api/chat', {
        method: 'POST', body: isMockMode ? { message } : { message, messageId, taskId }, schema: ChatReplySchema,
      }),
  })
}

export function useChatFeedback() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: (body: { messageId: string; outcome: 'resolved' | 'mentor' }) =>
      apiFetch('/api/chat/feedback', { method: 'POST', body, schema: Ok }),
    onSuccess: () => void cache.invalidateQueries({ queryKey: ['adaptation', 'metrics'] }),
  })
}
