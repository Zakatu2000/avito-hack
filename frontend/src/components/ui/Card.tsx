import type { HTMLAttributes, ReactNode } from 'react'

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  tone?: 'surface' | 'green' | 'blue' | 'purple' | 'red' | 'gray'
  flat?: boolean
  children: ReactNode
}

const TONE_CLASS: Record<NonNullable<CardProps['tone']>, string> = {
  surface: '',
  green: 'card--green',
  blue: 'card--blue',
  purple: 'card--purple',
  red: 'card--red',
  gray: 'card--gray',
}

export function Card({ tone = 'surface', flat, className, children, ...rest }: CardProps) {
  return (
    <div
      className={['card', TONE_CLASS[tone], flat ? 'card--flat' : '', className ?? '']
        .filter(Boolean)
        .join(' ')}
      {...rest}
    >
      {children}
    </div>
  )
}
