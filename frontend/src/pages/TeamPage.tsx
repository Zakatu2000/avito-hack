import { ApiError } from '../api/client'
import { useInterns } from '../api/hooks'
import { Card } from '../components/ui/Card'
import { ProgressBar } from '../components/ui/ProgressBar'
import { SkeletonCard } from '../components/ui/Skeleton'
import { ErrorState, NoAccess } from '../components/ui/States'
import { RequestsPage } from './RequestsPage'

export function TeamPage() {
  const interns = useInterns()

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
              {interns.data.map(({ user, progress, nextStepTitle }) => (
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
                </Card>
              ))}
            </div>
          </section>
          <RequestsPage />
        </>
      )}
    </div>
  )
}
