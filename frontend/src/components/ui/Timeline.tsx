import type { ReactNode } from 'react'
import type { BadgeTone } from './StatusBadge'

export interface TimelineStage {
  id: string
  title: string
  caption?: string
  tone: BadgeTone
  content: ReactNode
}

export function Timeline({ stages, ariaLabel }: { stages: TimelineStage[]; ariaLabel?: string }) {
  return (
    <ol className="timeline" aria-label={ariaLabel}>
      {stages.map((stage, index) => (
        <li className="timeline__item" key={stage.id}>
          <span className={`timeline__marker timeline__marker--${stage.tone}`} aria-hidden="true">
            {stage.tone === 'green' ? '✓' : index + 1}
          </span>
          <div className="timeline__head">
            <h3 className="heading-s">{stage.title}</h3>
            {stage.caption && <span className="caption">{stage.caption}</span>}
          </div>
          <div className="timeline__items">{stage.content}</div>
        </li>
      ))}
    </ol>
  )
}
