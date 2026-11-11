import { useKbArticles } from '../api/hooks'
import { SkeletonCard } from '../components/ui/Skeleton'
import { ErrorState } from '../components/ui/States'

export function KbPage() {
  const articles = useKbArticles()

  if (articles.isLoading) {
    return (
      <div className="page">
        <SkeletonCard lines={5} />
        <SkeletonCard lines={5} />
      </div>
    )
  }
  if (articles.isError || !articles.data) {
    return <ErrorState onRetry={() => void articles.refetch()} retryLoading={articles.isRefetching} />
  }

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="heading-l">База знаний</h1>
          <p className="body-secondary" style={{ marginTop: 4 }}>
            Короткие инструкции для первых недель
          </p>
        </div>
      </div>

      <div className="kb-banner" role="note">
        <span aria-hidden="true">⚠️</span>
        Тестовые данные, не регламент Авито
      </div>

      <div className="stack">
        {articles.data.map((article) => (
          <details key={article.id} className="article">
            <summary className="article__summary">
              <span>{article.title}</span>
              <span className="caption" style={{ whiteSpace: 'nowrap' }}>
                {article.duration}
              </span>
            </summary>
            <div className="article__body">
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {article.tags.map((tag) => (
                  <span key={tag} className="tag">
                    #{tag}
                  </span>
                ))}
              </div>
              <ol style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {article.steps.map((step, i) => (
                  <li key={i} className="article__step">
                    <span className="article__step-num" aria-hidden="true">
                      {i + 1}
                    </span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
              <p className="caption">Тестовые данные, не регламент Авито · обновлено {article.updated}</p>
            </div>
          </details>
        ))}
      </div>
    </div>
  )
}
