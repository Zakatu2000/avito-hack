import type { KnowledgeHit } from '../api/schemas'
import { Card } from './ui/Card'

export function KnowledgeResults({ hits }: { hits: KnowledgeHit[] }) {
  return <div className="stack">{hits.map((hit) => (
    <Card key={hit.chunkId}>
      <h3 className="heading-s">{hit.section}</h3>
      <p className="caption">{hit.title} · {hit.synthetic ? 'Учебный пример' : 'Подтверждённый источник'}
        {hit.estimatedMinutes ? ' · ' + hit.estimatedMinutes + ' мин' : ''}</p>
      <p>{hit.snippet}</p>
      {hit.url && <a href={hit.url} target="_blank" rel="noreferrer">Открыть источник</a>}
      {hit.sourceLocator && <p className="caption">{hit.sourceLocator}</p>}
    </Card>
  ))}</div>
}
