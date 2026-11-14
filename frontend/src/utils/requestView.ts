import type { LeaveReason, Request } from '../api/schemas'

export const NEW_REQUEST_LABELS = {
  technical_support: 'Техническая помощь', mentor_consultation: 'Консультация с наставником',
  learning_request: 'Запрос учебного материала',
} as const

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
  const payload = request.payload
  if (payload.kind === 'access') return 'Доступ: ' + payload.system
  const title = payload.kind === 'technical_support' ? payload.title : payload.topic
  return title ? NEW_REQUEST_LABELS[payload.kind] + ': ' + title : NEW_REQUEST_LABELS[payload.kind]
}

export function requestSubtitle(request: Request): string {
  if (request.payload.kind === 'leave') {
    return LEAVE_REASON_LABELS[request.payload.reason] + (request.payload.comment ? ` · ${request.payload.comment}` : '')
  }
  if (request.payload.kind === 'access') return request.payload.justification
  return (request.payload.kind === 'learning_request' ? request.payload.reason : request.payload.description) ?? ''
}

export function requestStatusBadgeLabel(request: Request): string | undefined {
  if (request.kind === 'access' && request.status === 'approved') return 'Выдан'
  return undefined
}
