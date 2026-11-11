import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { resetDb } from '../mocks/db'
import { useDevStore, type FailureMode } from '../stores/dev'
import { toast } from './ui/Toast'

const FAILURE_MODES: { value: FailureMode; label: string }[] = [
  { value: 'off', label: 'Выкл' },
  { value: 'always', label: 'Всегда' },
  { value: 'random', label: '50%' },
]

export function DevPanel() {
  const [open, setOpen] = useState(false)
  const failureMode = useDevStore((s) => s.failureMode)
  const setFailureMode = useDevStore((s) => s.setFailureMode)
  const latencyOverrideMs = useDevStore((s) => s.latencyOverrideMs)
  const setLatencyOverride = useDevStore((s) => s.setLatencyOverride)
  const queryClient = useQueryClient()

  return (
    <div className="dev-panel">
      {open && (
        <div className="dev-panel__body" role="dialog" aria-label="Панель разработчика">
          <div>
            <p className="dev-panel__label">Сбои сервисов</p>
            <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
              {FAILURE_MODES.map((mode) => (
                <button
                  key={mode.value}
                  type="button"
                  className={`btn btn--s ${failureMode === mode.value ? 'btn--primary' : 'btn--secondary'}`}
                  aria-pressed={failureMode === mode.value}
                  onClick={() => setFailureMode(mode.value)}
                >
                  {mode.label}
                </button>
              ))}
            </div>
          </div>
          <div className="dev-panel__row">
            <span className="dev-panel__label">Задержка</span>
            <select
              className="field__control"
              style={{ width: 120, padding: '4px 8px' }}
              value={latencyOverrideMs === null ? 'auto' : String(latencyOverrideMs)}
              onChange={(e) =>
                setLatencyOverride(e.target.value === 'auto' ? null : Number(e.target.value))
              }
              aria-label="Задержка ответа сервисов"
            >
              <option value="auto">авто 300–1200 мс</option>
              <option value="300">300 мс</option>
              <option value="1000">1000 мс</option>
            </select>
          </div>
          <button
            type="button"
            className="btn btn--s btn--secondary"
            onClick={() => {
              resetDb()
              void queryClient.invalidateQueries()
              toast('Демо-данные сброшены', 'success')
            }}
          >
            Сбросить демо-данные
          </button>
          <p className="dev-panel__hint">Панель имитации: задержки, сбои, сброс localStorage.</p>
        </div>
      )}
      <button
        type="button"
        className="icon-btn"
        aria-expanded={open}
        aria-label="Панель разработчика"
        title="Панель разработчика"
        onClick={() => setOpen((v) => !v)}
      >
        🎛
      </button>
    </div>
  )
}
