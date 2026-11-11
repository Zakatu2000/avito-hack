import { Link } from 'react-router-dom'
import { useChecklist, useMe, useRequests } from '../api/hooks'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { ErrorState } from '../components/ui/States'
import { ListItem } from '../components/ui/ListItem'
import { ProgressBar } from '../components/ui/ProgressBar'
import { SkeletonCard } from '../components/ui/Skeleton'
import { StatusBadge } from '../components/ui/StatusBadge'

const QUICK_ACTIONS = [
  { to: '/requests/new/leave', icon: '🏖', title: 'Оформить отгул', hint: 'даты и причина — за минуту', bg: 'var(--card-green)' },
  { to: '/requests/new/access', icon: '🔑', title: 'Запросить доступ', hint: 'Confluence, Jira и другие системы', bg: 'var(--card-blue)' },
  { to: '/chat', icon: '💬', title: 'Спросить AI-buddy', hint: 'бот знает частые вопросы', bg: 'var(--card-purple)' },
  { to: '/kb', icon: '📚', title: 'База знаний', hint: 'тестовые инструкции', bg: 'var(--card-gray)' },
]

export function HomePage() {
  const me = useMe()
  const checklist = useChecklist()
  const requests = useRequests()

  if (me.isLoading || checklist.isLoading) return <div className="page"><SkeletonCard lines={4} /><SkeletonCard lines={2} /></div>
  if (checklist.isError || !checklist.data) {
    return <ErrorState onRetry={() => void checklist.refetch()} retryLoading={checklist.isRefetching} />
  }

  const user = me.data
  const items = checklist.data.flatMap((stage) => stage.items)
  const done = items.filter((i) => i.status === 'done').length
  const percent = items.length ? Math.round((done / items.length) * 100) : 0
  const next = items.find((i) => i.status !== 'done')
  const deadlines = items.filter((i) => i.status !== 'done' && i.deadline).slice(0, 4)
  const isApprover = user?.role === 'mentor' || user?.role === 'lead'
  const queue = (requests.data ?? []).filter((r) => r.status === 'sent' || r.status === 'approving')

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="heading-l">
            Привет, {user?.name.split(' ')[0] ?? 'стажёр'} 👋
          </h1>
          <p className="body-secondary" style={{ marginTop: 4 }}>
            {isApprover
              ? 'Твоя команда и очередь согласования — под рукой'
              : 'Погнали осваиваться в команде — я подскажу, что дальше'}
          </p>
        </div>
      </div>

      <Card tone="green">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
          <h2 className="heading-s">Прогресс адаптации</h2>
          <span className="caption" style={{ fontWeight: 700 }}>
            {done} из {items.length} пунктов · {percent}%
          </span>
        </div>
        <ProgressBar value={percent} label="Прогресс адаптации" />
      </Card>

      {isApprover ? (
        <Card tone="purple">
          <h2 className="heading-s">Очередь согласования</h2>
          <p className="body" style={{ margin: '6px 0 14px' }}>
            {queue.length > 0
              ? `Ждут твоего решения: ${queue.length} ${queue.length === 1 ? 'запрос' : 'запроса'}`
              : 'Новых запросов нет — всё разобрано'}
          </p>
          <Link to="/team">
            <Button variant="secondary">Открыть вид команды</Button>
          </Link>
        </Card>
      ) : (
        next && (
          <Card tone="purple">
            <span className="caption" style={{ fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Следующий шаг
            </span>
            <h2 className="heading-m" style={{ margin: '6px 0' }}>
              {next.title}
            </h2>
            <p className="body" style={{ marginBottom: 16 }}>{next.nextStep}</p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {next.actionLink && (
                <Link to={next.actionLink}>
                  <Button>Действовать</Button>
                </Link>
              )}
              <Link to="/timeline">
                <Button variant="secondary">Весь план</Button>
              </Link>
            </div>
          </Card>
        )
      )}

      <section aria-label="Дедлайны" className="stack">
        <h2 className="section-title">Ближайшие дедлайны</h2>
        {deadlines.length === 0 && <p className="body-secondary">Дедлайнов нет — можно выдохнуть</p>}
        {deadlines.map((item) => (
          <ListItem
            key={item.id}
            icon="⏰"
            title={item.title}
            subtitle={item.deadline ?? undefined}
            right={<StatusBadge status={item.status} />}
          />
        ))}
      </section>

      <section aria-label="Быстрые действия">
        <h2 className="section-title" style={{ marginBottom: 16 }}>
          Быстрые действия
        </h2>
        <div className="grid-4">
          {QUICK_ACTIONS.map((action) => (
            <Link key={action.to} to={action.to} className="quick-action" style={{ background: action.bg }}>
              <span className="quick-action__icon" aria-hidden="true">
                {action.icon}
              </span>
              <span className="quick-action__title">{action.title}</span>
              <span className="quick-action__hint">{action.hint}</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
