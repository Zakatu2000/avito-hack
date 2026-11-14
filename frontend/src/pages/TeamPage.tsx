import { useFirstTask } from '../api/adaptation'
import { useState } from 'react'
import { ApiError, getErrorMessage } from '../api/client'
import { useApproveChecklistItem, useInterns, usePendingItems } from '../api/hooks'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { ListItem } from '../components/ui/ListItem'
import { ProgressBar } from '../components/ui/ProgressBar'
import { SkeletonCard } from '../components/ui/Skeleton'
import { ErrorState, NoAccess } from '../components/ui/States'
import { StatusBadge } from '../components/ui/StatusBadge'
import { toast } from '../components/ui/Toast'
import { RequestsPage } from './RequestsPage'

function PendingItemsSection() {
  const pending = usePendingItems()
  const approve = useApproveChecklistItem()
  const [approvingKey, setApprovingKey] = useState<string | null>(null)

  if (pending.isLoading) return <SkeletonCard lines={2} />
  if (pending.isError || !pending.data || pending.data.length === 0) return null

  return (
    <section aria-label="Пункты на подтверждение" className="stack">
      <h2 className="section-title">Пункты на подтверждение</h2>
      {pending.data.map((item) => {
        const key = `${item.userId}:${item.itemId}`
        return (
          <ListItem
            key={key}
            icon="⏳"
            title={`${item.userName}: ${item.title}`}
            subtitle={item.nextStep}
            right={
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <StatusBadge status="pending_approval" />
                <Button
                  size="s"
                  loading={approve.isPending && approvingKey === key}
                  onClick={() => {
                    setApprovingKey(key)
                    approve.mutate(
                      { itemId: item.itemId, userId: item.userId },
                      {
                        onSuccess: () => toast('Пункт подтверждён', 'success'),
                        onError: (err) => toast(getErrorMessage(err), 'error'),
                        onSettled: () => setApprovingKey(null),
                      },
                    )
                  }}
                >
                  Подтвердить
                </Button>
              </div>
            }
          />
        )
      })}
    </section>
  )
}

export function TeamPage() {
  const interns = useInterns()
  const firstTask = useFirstTask()

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="heading-l">Команда стажёров</h1>
          <p className="body-secondary" style={{ marginTop: 4 }}>
            Прогресс адаптации и очередь согласования в одном месте
          </p>
        </div>
      </div>

      {interns.isLoading && (
        <>
          <SkeletonCard lines={3} />
          <SkeletonCard lines={3} />
        </>
      )}
      {interns.isError &&
        (interns.error instanceof ApiError && interns.error.isForbidden ? (
          <NoAccess />
        ) : (
          <ErrorState onRetry={() => void interns.refetch()} retryLoading={interns.isRefetching} />
        ))}

      {interns.data && (
        <>
          <section aria-label="Стажёры" className="stack">
            <h2 className="section-title">Стажёры</h2>
            <div className="grid-2">
              {interns.data.map(({ user, progress, nextStepTitle, firstTaskStatus }) => (
                <Card key={user.id}>
                  <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
                    <span
                      aria-hidden="true"
                      style={{
                        width: 48,
                        height: 48,
                        borderRadius: '50%',
                        background: 'var(--card-purple)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 800,
                      }}
                    >
                      {user.initials}
                    </span>
                    <div>
                      <h3 className="heading-s">{user.name}</h3>
                      <p className="caption">{user.roleLabel}</p>
                    </div>
                  </div>
                  <ProgressBar value={progress.percent} label={`Прогресс ${user.name}`} />
                  <p className="caption" style={{ marginTop: 8 }}>
                    {progress.done}/{progress.total} пунктов · дальше: {nextStepTitle ?? 'всё готово 🎉'}
                  </p>
                  {(firstTaskStatus === 'unassigned' || firstTaskStatus === 'reported') &&
                    <Button size="s" loading={firstTask.isPending && firstTask.variables?.userId === user.id} onClick={() =>
                      firstTask.mutate({ userId: user.id, operation: firstTaskStatus === 'unassigned' ? 'assign' : 'confirm' },
                        { onError: (err) => toast(getErrorMessage(err), 'error') })
                    }>{firstTaskStatus === 'unassigned' ? 'Назначить учебную задачу' : 'Подтвердить старт'}</Button>}
                  {firstTaskStatus === 'assigned' && <p className="caption">Учебная задача назначена</p>}
                  {firstTaskStatus === 'confirmed' && <p className="caption">Самостоятельный старт подтверждён</p>}
                </Card>
              ))}
            </div>
          </section>
          <PendingItemsSection />
          <RequestsPage />
        </>
      )}
    </div>
  )
}
