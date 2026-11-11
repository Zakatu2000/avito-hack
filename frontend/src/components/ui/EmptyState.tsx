import type { ReactNode } from 'react'

export interface EmptyStateProps {
  icon?: string
  title: string
  hint?: string
  action?: ReactNode
}

export function EmptyState({ icon = '🗂', title, hint, action }: EmptyStateProps) {
  return (
    <div className="empty">
      <div className="empty__icon" aria-hidden="true">
        {icon}
      </div>
      <div className="empty__title">{title}</div>
      {hint && <div className="empty__hint">{hint}</div>}
      {action}
    </div>
  )
}
