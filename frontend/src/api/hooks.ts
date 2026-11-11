import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { service, type AccessSystem } from '../services'
import { useAuthStore } from '../stores/auth'
import type { AccessRequestInput, ItemStatus, LeaveRequestInput, Request } from './schemas'

export function useMe() {
  const userId = useAuthStore((s) => s.userId)
  return useQuery({ queryKey: ['me', userId], queryFn: () => service.getMe(), enabled: !!userId })
}

export function useUsers() {
  return useQuery({ queryKey: ['users'], queryFn: () => service.getUsers() })
}

export function useChecklist() {
  const userId = useAuthStore((s) => s.userId)
  return useQuery({
    queryKey: ['checklist', userId],
    queryFn: () => service.getChecklist(),
    enabled: !!userId,
  })
}

export function useUpdateItemStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ itemId, status }: { itemId: string; status: ItemStatus }) =>
      service.updateItemStatus(itemId, status),
    onSuccess: (checklist) => qc.setQueryData(['checklist', useAuthStore.getState().userId], checklist),
  })
}

export function useRequests(scope?: 'queue') {
  const userId = useAuthStore((s) => s.userId)
  return useQuery({
    queryKey: ['requests', scope ?? 'all', userId],
    queryFn: () => service.listRequests(scope),
    enabled: !!userId,
  })
}

function useInvalidateRequests() {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ queryKey: ['requests'] })
    void qc.invalidateQueries({ queryKey: ['interns'] })
  }
}

export function useCreateLeaveRequest() {
  const invalidate = useInvalidateRequests()
  return useMutation({
    mutationFn: (input: LeaveRequestInput) => service.createLeaveRequest(input),
    onSuccess: invalidate,
  })
}

export function useCreateAccessRequest() {
  const invalidate = useInvalidateRequests()
  return useMutation({
    mutationFn: (input: AccessRequestInput) => service.requestAccess(input),
    onSuccess: invalidate,
  })
}

export function useApproveRequest() {
  const invalidate = useInvalidateRequests()
  return useMutation({
    mutationFn: (id: string) => service.approveRequest(id),
    onSuccess: invalidate,
  })
}

export function useRejectRequest() {
  const invalidate = useInvalidateRequests()
  return useMutation({
    mutationFn: ({ id, comment }: { id: string; comment?: string }) =>
      service.rejectRequest(id, comment),
    onSuccess: invalidate,
  })
}

export function useSendRequest() {
  const invalidate = useInvalidateRequests()
  return useMutation({
    mutationFn: (id: string) => service.sendRequest(id),
    onSuccess: invalidate,
  })
}

export function useContacts() {
  const userId = useAuthStore((s) => s.userId)
  return useQuery({
    queryKey: ['contacts', userId],
    queryFn: () => service.getContacts(),
    enabled: !!userId,
  })
}

export function useKbArticles() {
  const userId = useAuthStore((s) => s.userId)
  return useQuery({ queryKey: ['kb'], queryFn: () => service.getKbArticles(), enabled: !!userId })
}

export function useAccessSystems() {
  const userId = useAuthStore((s) => s.userId)
  return useQuery({
    queryKey: ['access-systems'],
    queryFn: () => service.getAccessSystems(),
    enabled: !!userId,
  })
}

export function useMetrics() {
  const userId = useAuthStore((s) => s.userId)
  return useQuery({ queryKey: ['metrics'], queryFn: () => service.getMetrics(), enabled: !!userId })
}

export function useInterns() {
  const userId = useAuthStore((s) => s.userId)
  return useQuery({ queryKey: ['interns'], queryFn: () => service.getInterns(), enabled: !!userId })
}

export function useSendChatMessage() {
  return useMutation({ mutationFn: (message: string) => service.sendChatMessage(message) })
}

export type { AccessSystem, Request }
