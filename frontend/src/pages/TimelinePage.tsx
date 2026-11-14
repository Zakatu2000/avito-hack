import { isMockMode } from '../api/auth'
import { AdaptationPlanPage } from './AdaptationPlanPage'
import { useState } from 'react'
import { getErrorMessage } from '../api/client'
import { useChecklist, useMe, useUpdateItemStatus } from '../api/hooks'
import type { ChecklistItem, ChecklistStage, ItemStatus } from '../api/schemas'
import { Button } from '../components/ui/Button'
import { ErrorState } from '../components/ui/States'
import { ListItem } from '../components/ui/ListItem'
import { ProgressBar } from '../components/ui/ProgressBar'
import { SkeletonCard } from '../components/ui/Skeleton'
import { StatusBadge } from '../components/ui/StatusBadge'
import { Timeline } from '../components/ui/Timeline'
import { toast } from '../components/ui/Toast'

const ITEM_ICONS: Record<ItemStatus, string> = {
  not_started: '⬜',
  in_progress: '🔄',
  pending_approval: '⏳',
  done: '✅',
}

function stageTone(stage: ChecklistStage): 'gray' | 'blue' | 'purple' | 'green' {
  const statuses = stage.items.map((i) => i.status)
  if (statuses.every((s) => s === 'done')) return 'green'
  if (statuses.includes('pending_approval')) return 'purple'
  if (statuses.includes('in_progress')) return 'blue'
  return 'gray'
}

function ItemActions({
  item,
  isApprover,
  loading,
  onChange,
}: {
  item: ChecklistItem
  isApprover: boolean
  loading: boolean
  onChange: (status: ItemStatus) => void
}) {
  if (item.status === 'done') return <StatusBadge status="done" />
  if (item.status === 'pending_approval' || isApprover) return <StatusBadge status={item.status} />
  if (item.status === 'not_started') {
    return (
      <Button size="s" variant="secondary" loading={loading} onClick={() => onChange('in_progress')}>
        Начать
      </Button>
    )
  }
  return (
    <Button
      size="s"
      variant="secondary"
      loading={loading}
      onClick={() => onChange(item.requiresApproval ? 'pending_approval' : 'done')}
    >
      {item.requiresApproval ? 'На проверку' : 'Готово'}
    </Button>
  )
}

export function TimelinePage() {
  return isMockMode ? <MockTimelinePage /> : <AdaptationPlanPage />
}

function MockTimelinePage() {
  const me = useMe()
  const checklist = useChecklist()
  const updateItem = useUpdateItemStatus()
  const [pendingId, setPendingId] = useState<string | null>(null)
  const isApprover = me.data?.role === 'mentor' || me.data?.role === 'lead'

  if (checklist.isLoading) {
    return (
      <div className="page">
        <SkeletonCard lines={5} />
        <SkeletonCard lines={5} />
      </div>
    )
  }
  if (checklist.isError || !checklist.data) {
    return (
      <ErrorState
        onRetry={() => void checklist.refetch()}
        retryLoading={checklist.isRefetching}
      />
    )
  }

  const items = checklist.data.flatMap((s) => s.items)
  const done = items.filter((i) => i.status === 'done').length
  const percent = items.length ? Math.round((done / items.length) * 100) : 0

  const changeStatus = (item: ChecklistItem, status: ItemStatus) => {
    setPendingId(item.id)
    updateItem.mutate(
      { itemId: item.id, status },
      {
        onSuccess: () => toast('Статус обновлён', 'success'),
        onError: (err) => toast(getErrorMessage(err), 'error'),
        onSettled: () => setPendingId(null),
      },
    )
  }

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="heading-l">Путь адаптации</h1>
          <p className="body-secondary" style={{ marginTop: 4 }}>
            От первой недели до выпускного — {items.length} шагов
          </p>
        </div>
        <span className="caption" style={{ fontWeight: 700 }}>
          {done} из {items.length} · {percent}%
        </span>
      </div>
      <ProgressBar value={percent} label="Общий прогресс адаптации" />

      <Timeline
        ariaLabel="Этапы адаптации"
        stages={checklist.data.map((stage) => {
          const stageDone = stage.items.filter((i) => i.status === 'done').length
          return {
            id: stage.id,
            title: stage.title,
            caption: `${stage.period} · ${stageDone}/${stage.items.length}`,
            tone: stageTone(stage),
            content: stage.items.map((item) => (
              <ListItem
                key={item.id}
                icon={ITEM_ICONS[item.status]}
                title={
                  <span style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    {item.title}
                    <StatusBadge status={item.status} />
                  </span>
                }
                subtitle={item.status === 'done' ? item.description : item.nextStep}
                right={
                  <ItemActions
                    item={item}
                    isApprover={!!isApprover}
                    loading={updateItem.isPending && pendingId === item.id}
                    onChange={(status) => changeStatus(item, status)}
                  />
                }
              />
            )),
          }
        })}
      />

      {isApprover && (
        <p className="caption">
          Пункты стажёров в статусе «Ждёт согласования» подтверждай в разделе «Команда».
        </p>
      )}
    </div>
  )
}
