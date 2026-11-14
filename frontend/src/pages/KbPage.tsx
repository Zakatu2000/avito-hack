import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useKnowledgeSearch } from '../api/adaptation'
import { isMockMode } from '../api/auth'
import { KnowledgeResults } from '../components/KnowledgeResults'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { useKbArticles } from '../api/hooks'
import { SkeletonCard } from '../components/ui/Skeleton'
import { ErrorState } from '../components/ui/States'

function KnowledgeSearch() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const category = params.get('category') ?? ''
  const [draft, setDraft] = useState(q)
  const [selection, setSelection] = useState(category)
  const results = useKnowledgeSearch(q, category, '', params.get('taskId') ?? '')
  return <section className="stack" aria-label="Поиск по базе знаний">
    <form className="page__actions" onSubmit={(event) => {
      event.preventDefault(); setParams({ q: draft.trim(), ...(selection ? { category: selection } : {}) })
    }}>
      <Input label="Поиск материалов" name="kb-query" value={draft} maxLength={500} onChange={(event) => setDraft(event.target.value)} />
      <Select label="Тип источника" name="category" value={selection} onChange={(event) => setSelection(event.target.value)} options={[
        { value: '', label: 'Все' }, { value: 'normative', label: 'Чек-лист и кейс' },
        { value: 'reference', label: 'Справочники' }, { value: 'educational', label: 'Учебные материалы' },
        { value: 'public_context', label: 'Открытые материалы' },
      ]} />
      <Button type="submit" loading={results.isFetching} disabled={!draft.trim()}>Найти</Button>
    </form>
    {results.isError && <ErrorState onRetry={() => void results.refetch()} retryLoading={results.isRefetching} />}
    {results.data?.length === 0 && <p>Материалы по этому запросу не найдены.</p>}
    {results.data && <KnowledgeResults hits={results.data} />}
  </section>
}

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

      {!isMockMode && <KnowledgeSearch />}

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
