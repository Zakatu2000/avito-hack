import { useEffect, useId, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

export interface OverlayProps {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  variant?: 'modal' | 'sheet'
}

export function Overlay({ open, title, onClose, children, footer, variant = 'modal' }: OverlayProps) {
  const titleId = useId()
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null
  return createPortal(
    <div
      className={`overlay ${variant === 'sheet' ? 'overlay--sheet' : ''}`}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="overlay__dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="overlay__head">
          <h2 className="overlay__title" id={titleId}>
            {title}
          </h2>
          <button type="button" className="overlay__close" onClick={onClose} aria-label="Закрыть">
            ✕
          </button>
        </div>
        {children}
        {footer && <div style={{ marginTop: 20, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>{footer}</div>}
      </div>
    </div>,
    document.body,
  )
}

export function Modal(props: Omit<OverlayProps, 'variant'>) {
  return <Overlay {...props} variant="modal" />
}

export function BottomSheet(props: Omit<OverlayProps, 'variant'>) {
  return <Overlay {...props} variant="sheet" />
}
