import type { ItemStatus, RequestStatus } from '../../api/schemas'

export type BadgeTone = 'gray' | 'blue' | 'green' | 'purple' | 'red'

const STATUS_CONFIG: Record<ItemStatus | RequestStatus, { label: string; tone: BadgeTone }> = {
  not_started: { label: 'Не начато', tone: 'gray' },
  in_progress: { label: 'В процессе', tone: 'blue' },
  pending_approval: { label: 'Ждёт согласования', tone: 'purple' },
  done: { label: 'Готово', tone: 'green' },
  draft: { label: 'Черновик', tone: 'gray' },
  sent: { label: 'Отправлен', tone: 'blue' },
  approving: { label: 'На согласовании', tone: 'purple' },
  approved: { label: 'Одобрен', tone: 'green' },
  resolved: { label: 'Решение предложено', tone: 'green' },
  closed: { label: 'Закрыт', tone: 'green' },
  awaiting_confirmation: { label: 'Ожидается ответ стажёра', tone: 'purple' },
  scheduled: { label: 'Время согласовано', tone: 'blue' },
  completed: { label: 'Завершён', tone: 'green' },
  rejected: { label: 'Отклонён', tone: 'red' },
}

export interface StatusBadgeProps {
  status: ItemStatus | RequestStatus
  label?: string
  className?: string
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const cfg = STATUS_CONFIG[status]
  return (
    <span className={`badge badge--${cfg.tone} ${className ?? ''}`.trim()}>
      <span className="badge__dot" aria-hidden="true" />
      {label ?? cfg.label}
    </span>
  )
}

export function statusTone(status: ItemStatus | RequestStatus): BadgeTone {
  return STATUS_CONFIG[status].tone
}

export function statusLabel(status: ItemStatus | RequestStatus): string {
  return STATUS_CONFIG[status].label
}
