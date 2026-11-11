import { create } from 'zustand'

export interface ToastItem {
  id: string
  message: string
  tone: 'info' | 'success' | 'error'
}

interface ToastState {
  toasts: ToastItem[]
  push: (message: string, tone?: ToastItem['tone']) => void
  dismiss: (id: string) => void
}

function makeId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `t-${Date.now()}-${Math.round(Math.random() * 1e6)}`
}

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: (message, tone = 'info') => {
    const id = makeId()
    set({ toasts: [...get().toasts, { id, message, tone }] })
    setTimeout(() => get().dismiss(id), 4200)
  },
  dismiss: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
}))

export function toast(message: string, tone: ToastItem['tone'] = 'info') {
  useToastStore.getState().push(message, tone)
}

export function ToastPort() {
  const toasts = useToastStore((s) => s.toasts)
  const dismiss = useToastStore((s) => s.dismiss)
  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast--${t.tone}`}>
          <span aria-hidden="true">{t.tone === 'success' ? '✓' : t.tone === 'error' ? '⚠' : 'ℹ'}</span>
          <span style={{ flex: 1 }}>{t.message}</span>
          <button
            type="button"
            onClick={() => dismiss(t.id)}
            aria-label="Скрыть уведомление"
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', font: 'inherit' }}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
