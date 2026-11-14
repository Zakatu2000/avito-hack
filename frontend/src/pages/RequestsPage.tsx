import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { isMockMode } from '../api/auth'
import { getErrorMessage } from '../api/client'
import {
  useApproveRequest,
  useMe,
  useRejectRequest,
  useRequests,
  useSendRequest,
} from '../api/hooks'
import type { Request as BuddyRequest } from '../api/schemas'
import { PortalRequestActions } from '../components/PortalRequestActions'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { ListItem } from '../components/ui/ListItem'
import { Modal } from '../components/ui/Overlay'
import { SkeletonCard } from '../components/ui/Skeleton'
import { ErrorState } from '../components/ui/States'
import { StatusBadge } from '../components/ui/StatusBadge'
import { toast } from '../components/ui/Toast'
import { Textarea } from '../components/ui/Input'
import { NEW_REQUEST_LABELS, requestStatusBadgeLabel, requestSubtitle, requestTitle } from '../utils/requestView'

function formatTime(value: string) {
  return new Date(value).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

function TicketDetails({ request }: { request: BuddyRequest }) {
  const preferred = request.payload.kind === 'mentor_consultation' ? request.payload.preferredAt : undefined
  return <>
    {request.assignee && <p>Ответственный: {request.assignee.name}</p>}
    {preferred && <p>Предпочтительное время: {formatTime(preferred)}</p>}
    {request.proposedAt && <p>Предложенное время: {formatTime(request.proposedAt)}</p>}
    {request.scheduledAt && <p>Согласованное время: {formatTime(request.scheduledAt)} · демо</p>}
    {request.taskId && <Link to={'/timeline#' + request.taskId}>Связанный пункт адаптации</Link>}
    {request.result && <div><p>{request.result.text}</p>{request.result.url?.startsWith('https://') &&
      <a href={request.result.url} target="_blank" rel="noreferrer">Ссылка от наставника</a>}</div>}
  </>
}

function History({ request }: { request: BuddyRequest }) {
  return (
    <div className="history">
      {request.history.map((entry, i) => (
        <div key={i} className="history__row">
          <strong>{entry.status}</strong>
          <span>· {entry.by}</span>
          <span>· {new Date(entry.at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })}</span>
          {entry.scheduledAt && <span>· {formatTime(entry.scheduledAt)}</span>}
          {entry.comment && <span>· «{entry.comment}»</span>}
        </div>
      ))}
    </div>
  )
}

function QueueSection() {
  const queue = useRequests('queue')
  const approve = useApproveRequest()
  const reject = useRejectRequest()
  const [rejecting, setRejecting] = useState<BuddyRequest | null>(null)
  const [comment, setComment] = useState('')

  if (queue.isLoading) return <SkeletonCard lines={3} />
  if (queue.isError || !queue.data) return null
  const items = queue.data

  const runApprove = (id: string) => {
    approve.mutate(id, {
      onSuccess: (r) => toast(r.status === 'approved' ? 'Запрос закрыт' : 'Передан дальше', 'success'),
      onError: (err) => toast(getErrorMessage(err), 'error'),
    })
  }

  return (
    <section aria-label="Очередь согласования" className="stack">
      <h2 className="section-title">Очередь согласования</h2>
      {items.length === 0 && (
        <EmptyState icon="✅" title="Очередь пуста" hint="Новых запросов от стажёров нет" />
      )}
      {items.map((request) => request.allowedActions ? (
        <div key={request.id} className="stack">
          <ListItem icon="📋" title={request.authorName + ': ' + requestTitle(request)} subtitle={requestSubtitle(request)}
            right={<StatusBadge status={request.status} />} />
          <TicketDetails request={request} />
          <PortalRequestActions request={request} />
        </div>
      ) : (
        <div key={request.id} className="stack">
          <ListItem
            icon={request.kind === 'leave' ? '🏖' : request.kind === 'access' ? '🔑' : '📋'}
            title={`${request.authorName}: ${requestTitle(request)}`}
            subtitle={requestSubtitle(request)}
            right={
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <Button size="s" loading={approve.isPending && approve.variables === request.id} onClick={() => runApprove(request.id)}>
                  {request.status === 'sent' ? 'Согласовать' : 'Вынести решение'}
                </Button>
                <Button
                  size="s"
                  variant="danger"
                  onClick={() => {
                    setRejecting(request)
                    setComment('')
                  }}
                >
                  Отклонить
                </Button>
              </div>
            }
          />
        </div>
      ))}
      <Modal
        open={!!rejecting}
        title="Отклонить запрос"
        onClose={() => setRejecting(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setRejecting(null)}>
              Отмена
            </Button>
            <Button
              variant="danger"
              loading={reject.isPending}
              onClick={() => {
                if (!rejecting) return
                reject.mutate(
                  { id: rejecting.id, comment: comment || undefined },
                  {
                    onSuccess: () => {
                      toast('Запрос отклонён', 'success')
                      setRejecting(null)
                    },
                    onError: (err) => toast(getErrorMessage(err), 'error'),
                  },
                )
              }}
            >
              Отклонить
            </Button>
          </>
        }
      >
        <Textarea
          label="Причина (необязательно)"
          placeholder="Например: нужны точные даты"
          rows={3}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          name="reject-comment"
        />
      </Modal>
    </section>
  )
}

export function RequestsPage() {
  const me = useMe()
  const requests = useRequests()
  const sendRequest = useSendRequest()
  const navigate = useNavigate()
  const { hash } = useLocation()
  const isApprover = me.data?.role === 'mentor' || me.data?.role === 'lead'

  if (requests.isLoading) {
    return (
      <div className="page">
        <SkeletonCard lines={4} />
        <SkeletonCard lines={2} />
      </div>
    )
  }
  if (requests.isError || !requests.data) {
    return <ErrorState onRetry={() => void requests.refetch()} retryLoading={requests.isRefetching} />
  }

  const sorted = [...requests.data].sort((a, b) => b.createdAt.localeCompare(a.createdAt))

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="heading-l">{isApprover ? 'Все запросы' : 'Мои запросы'}</h1>
          <p className="body-secondary" style={{ marginTop: 4 }}>
            Запросы, статусы и история решений
          </p>
        </div>
        <div className="page__actions">
          <Button onClick={() => navigate('/requests/new/leave')}>Оформить отгул</Button>
          <Button variant="secondary" onClick={() => navigate('/requests/new/access')}>
            Запросить доступ
          </Button>
          {!isMockMode && !isApprover && Object.entries(NEW_REQUEST_LABELS).map(([kind, label]) => (
            <Link key={kind} className="btn btn--secondary" to={'/requests/new/' + kind}>{label}</Link>
          ))}
        </div>
      </div>

      {isApprover && <QueueSection />}

      <section aria-label="Список запросов" className="stack">
        {sorted.length === 0 && (
          <EmptyState
            icon="📭"
            title="Запросов пока нет"
            hint="Оформи отгул или запроси доступ — они появятся здесь и переживут перезагрузку"
            action={
              <Link to="/requests/new/leave">
                <Button size="s">Оформить отгул</Button>
              </Link>
            }
          />
        )}
        {sorted.map((request) => (
          <details key={request.id} id={request.id} open={hash === '#' + request.id ? true : undefined} className="list-item" style={{ display: 'block', cursor: 'pointer' }}>
            <summary style={{ display: 'flex', alignItems: 'center', gap: 16, listStyle: 'none' }} aria-label={`Запрос: ${requestTitle(request)}`}>
              <span className="list-item__icon" aria-hidden="true">
                {request.kind === 'leave' ? '🏖' : request.kind === 'access' ? '🔑' : '📋'}
              </span>
              <span className="list-item__body">
                <span className="list-item__title">
                  {isApprover && request.authorId !== me.data?.id ? `${request.authorName}: ` : ''}
                  {requestTitle(request)}
                </span>
                <span className="list-item__subtitle">
                  {request.allowedActions ? (request.assignee?.name ?? 'Портал') : 'Согласуют: ' + request.approvers.join(', ')}
                </span>
              </span>
              <span className="list-item__right">
                {request.status === 'draft' && !request.allowedActions && (
                  <Button
                    size="s"
                    loading={sendRequest.isPending && sendRequest.variables === request.id}
                    onClick={(e) => {
                      e.preventDefault()
                      sendRequest.mutate(request.id, {
                        onSuccess: () => toast('Запрос отправлен', 'success'),
                        onError: (err) => toast(getErrorMessage(err), 'error'),
                      })
                    }}
                  >
                    Отправить
                  </Button>
                )}
                <StatusBadge status={request.status} label={requestStatusBadgeLabel(request)} />
              </span>
            </summary>
            <div style={{ marginTop: 12 }} className="stack">
              <p className="caption">{requestSubtitle(request)}</p>
              <TicketDetails request={request} />
              <History request={request} />
              {request.allowedActions && (!isApprover || request.status === 'draft') && <PortalRequestActions request={request} />}
            </div>
          </details>
        ))}
      </section>
    </div>
  )
}
