import type { LeaveReason, Request } from '../api/schemas'

export const LEAVE_REASON_LABELS: Record<LeaveReason, string> = {
  vacation: 'Отпуск',
  sick: 'Болезнь',
  personal: 'Личное',
  other: 'Другое',
}

export function formatDateRu(iso: string): string {
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y}`
}

export function requestTitle(request: Request): string {
  if (request.payload.kind === 'leave') {
    const { startDate, endDate } = request.payload
    return `Отгул: ${formatDateRu(startDate)} — ${formatDateRu(endDate)}`
  }
  return `Доступ: ${request.payload.system}`
}

export function requestSubtitle(request: Request): string {
  if (request.payload.kind === 'leave') {
    return LEAVE_REASON_LABELS[request.payload.reason] + (request.payload.comment ? ` · ${request.payload.comment}` : '')
  }
  return request.payload.justification
}

export function requestStatusBadgeLabel(request: Request): string | undefined {
  if (request.kind === 'access' && request.status === 'approved') return 'Выдан'
  return undefined
}
