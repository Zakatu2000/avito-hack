import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAdaptationPlan, useCatalogTransition, useFirstTask } from '../api/adaptation'
import { getErrorMessage } from '../api/client'
import { useMe, useUpdateItemStatus } from '../api/hooks'
import type { PlanItem } from '../api/schemas'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { ProgressBar } from '../components/ui/ProgressBar'
import { ErrorState } from '../components/ui/States'
import { StatusBadge } from '../components/ui/StatusBadge'

function PlanActions({ item, canUpdate }: { item: PlanItem; canUpdate: boolean }) {
  const legacy = useUpdateItemStatus()
  const catalog = useCatalogTransition()
  const first = useFirstTask()
  const [evidence, setEvidence] = useState('')
  const [opened, setOpened] = useState<{ title: string; description: string }>()
  const [error, setError] = useState('')
  const canWork = item.canWork && !item.blockers.length && canUpdate
  const failed = (err: unknown) => setError(getErrorMessage(err))
  const pending = legacy.isPending || catalog.isPending || first.isPending

  const open = () => {
    setError('')
    first.mutate({ operation: 'open' }, {
      onSuccess: (result) => { if ('title' in result) setOpened(result) }, onError: failed,
    })
  }
  const transition = () => {
    setError('')
    if (item.origin === 'portal') {
      legacy.mutate({ itemId: item.id, status: item.status === 'not_started' ? 'in_progress' : item.requiresApproval ? 'pending_approval' : 'done' }, { onError: failed })
    } else {
      catalog.mutate({ id: item.id, target: item.status === 'not_started' ? 'in_progress' : 'completed', evidenceUri: evidence || undefined }, { onError: failed })
    }
  }
  const evidenceRequired = item.origin === 'catalog' && item.completionPolicy === 'evidence_required' && item.status === 'in_progress'
  return <>
    {canWork && item.origin === 'assignment' && item.id === 'first-task' &&
      <Button size="s" loading={pending} onClick={open}>Открыть учебную задачу</Button>}
    {opened && canWork && <Card><h4>{opened.title}</h4><p>{opened.description}</p><span className="caption">Учебная задача · демо</span></Card>}
    {canWork && item.id === 'solo-start' && item.status === 'not_started' &&
      <Button size="s" loading={pending} onClick={() => {
        setError(''); first.mutate({ operation: 'start' }, { onError: failed })
      }}>Отметить начало работы</Button>}
    {canWork && item.origin !== 'assignment' && item.id !== 'wk1-access' && (item.status === 'not_started' || item.status === 'in_progress') && <>
      {evidenceRequired && <Input label="Ссылка на подтверждение" name={'evidence-' + item.id} type="url" value={evidence} onChange={(event) => setEvidence(event.target.value)} />}
      <Button size="s" loading={pending} disabled={evidenceRequired && !evidence} onClick={transition}>
        {item.status === 'not_started' ? 'Начать' : item.origin === 'portal' && item.requiresApproval ? 'На проверку' : 'Готово'}
      </Button>
    </>}
    {error && <p role="alert">{error}</p>}
  </>
}

function PlanRow({ item, canUpdate, compact = false }: { item: PlanItem; canUpdate: boolean; compact?: boolean }) {
  return <div className="plan-item stack" id={compact ? undefined : item.id}>
    <div className="page__actions"><strong>{item.title}</strong><StatusBadge status={item.status} /></div>
    {!compact && <p className="caption">{item.sources.join(' · ')}{item.deadline ? ' · ' + item.deadline : ''}</p>}
    {item.status !== 'done' && item.nextStep && !item.blockers.length && <p>{item.nextStep}</p>}
    {item.completionCriteria && !compact && <p className="caption">{item.completionCriteria}</p>}
    {item.status !== 'done' && item.blockers.map((blocker) => <p key={blocker.reason} className="caption">{blocker.reason}</p>)}
    {item.requests.length > 0 && <div className="page__actions">{item.requests.map((request) => (
      <Link key={request.id} to={'/requests#' + request.id}><StatusBadge status={request.status} /></Link>
    ))}</div>}
    <div className="page__actions">
      {item.actionLink && !item.blockers.length && <Link to={item.actionLink}>Открыть материалы</Link>}
      <Link to={'/chat?task=' + encodeURIComponent(item.id)}>Помоги выполнить этот шаг</Link>
      <PlanActions item={item} canUpdate={canUpdate} />
    </div>
  </div>
}

export function AdaptationPlanPage() {
  const plan = useAdaptationPlan()
  const me = useMe()
  const { hash } = useLocation()
  if (plan.isPending) return <p role="status">Загружаем путь адаптации…</p>
  if (!plan.data) return <ErrorState onRetry={() => void plan.refetch()} retryLoading={plan.isRefetching} />
  const { quickStart, blockers, nextStep, items } = plan.data
  const done = quickStart.filter((group) => group.done).length
  const stages = Array.from(new Set(items.map((item) => item.stage)))
  const canUpdate = me.data?.role === 'intern'
  return <div className="page">
    <h1 className="heading-l">Путь адаптации</h1>
    {nextStep && <Card tone="purple"><h2 className="heading-s">Следующий шаг</h2><p>{nextStep.title}</p>
      <Link to={'/timeline#' + nextStep.id}>Перейти к шагу</Link></Card>}
    <Card><h2 className="heading-s">Быстрый старт</h2>
      <p>{done} из {quickStart.length} шагов</p>
      <ProgressBar value={done / quickStart.length * 100} label="Прогресс быстрого старта" />
      <ol className="quick-start">{quickStart.map((group) => <li key={group.id}>
        <h3 className="heading-s">{group.title} {group.done && <StatusBadge status="done" />}</h3>
        {group.items.map((item) => <PlanRow key={item.id} item={item} compact canUpdate={canUpdate} />)}
      </li>)}</ol>
    </Card>
    {blockers.length > 0 && <Card><h2 className="heading-s">Что мешает начать работу</h2>
      <ul className="plan-blockers">{blockers.map((blocker) => <li key={blocker.itemId + blocker.reason}>
        <strong>{blocker.title}</strong> · {blocker.reason} <Link to={blocker.action}>Что сделать</Link>
      </li>)}</ul>
    </Card>}
    <details className="card" open={hash ? true : undefined}>
      <summary className="heading-s">Полная программа адаптации</summary>
      {stages.map((stage) => {
        const group = items.filter((item) => item.stage === stage)
        return <details className="plan-stage" key={stage} open={group.some((item) => '#' + item.id === hash) ? true : undefined}>
          <summary>{group[0].stageLabel} · {group.filter((item) => item.status === 'done').length}/{group.length}</summary>
          {group.map((item) => <PlanRow key={item.id} item={item} canUpdate={canUpdate} />)}
        </details>
      })}
    </details>
  </div>
}
