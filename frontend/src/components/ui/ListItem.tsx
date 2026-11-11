import type { ReactNode } from 'react'

export interface ListItemProps {
  icon?: ReactNode
  title: ReactNode
  subtitle?: ReactNode
  right?: ReactNode
  className?: string
}

export function ListItem({ icon, title, subtitle, right, className }: ListItemProps) {
  return (
    <div className={`list-item ${className ?? ''}`.trim()}>
      {icon !== undefined && <div className="list-item__icon">{icon}</div>}
      <div className="list-item__body">
        <div className="list-item__title">{title}</div>
        {subtitle && <div className="list-item__subtitle">{subtitle}</div>}
      </div>
      {right && <div className="list-item__right">{right}</div>}
    </div>
  )
}
