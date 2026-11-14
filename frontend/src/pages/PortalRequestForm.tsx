import { useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useAdaptationPlan, useCreatePortalRequest, useKnowledgeSearch, usePortalRequestAction } from '../api/adaptation'
import { isMockMode } from '../api/auth'
import { getErrorMessage } from '../api/client'
import { useRequests } from '../api/hooks'
import { NewRequestInputSchemas, NewRequestKindSchema, SupportCategorySchema, type NewRequestKind, type Request } from '../api/schemas'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input, Textarea } from '../components/ui/Input'
import { KnowledgeResults } from '../components/KnowledgeResults'
import { Select } from '../components/ui/Select'

import { NEW_REQUEST_LABELS } from '../utils/requestView'
const categories = [
  { value: 'environment', label: 'Рабочее окружение' }, { value: 'software', label: 'Корпоративное ПО' },
  { value: 'network', label: 'VPN и сеть' }, { value: 'git', label: 'Git и репозиторий' },
  { value: 'other', label: 'Другая проблема' },
]
const priorities = [{ value: 'low', label: 'Низкий' }, { value: 'normal', label: 'Обычный' }, { value: 'high', label: 'Высокий' }]
const tracks = [{ value: 'backend', label: 'Backend' }, { value: 'analytics', label: 'Аналитика' }, { value: 'marketing', label: 'Маркетинг' }]

function localInput(value?: string) {
  if (!value) return ''
  const time = new Date(value)
  return new Date(time.getTime() - time.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

function RequestForm({ kind, existing }: { kind: NewRequestKind; existing?: Request }) {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const task = existing?.taskId ?? params.get('task') ?? ''
  const plan = useAdaptationPlan()
  const [fields, setFields] = useState<Record<string, string>>(() => {
    const values = Object.fromEntries(Object.entries(existing?.payload ?? {}).filter((entry): entry is [string, string] => entry[0] !== 'kind' && typeof entry[1] === 'string'))
    const category = SupportCategorySchema.safeParse(params.get('category'))
    const suggested = !existing && kind === 'technical_support' && category.success ? category.data : ''
    return { priority: 'normal', topic: params.get('topic') ?? '', category: suggested, ...values, taskId: task,
      preferredAt: localInput(values.preferredAt) }
  })
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [searchedFor, setSearchedFor] = useState('')
  const track = fields.track || plan.data?.track || 'backend'
  const knowledge = useKnowledgeSearch(search, '', track)
  const create = useCreatePortalRequest()
  const change = usePortalRequestAction()
  const pending = create.isPending || change.isPending
  const attempt = useRef({ fingerprint: '', key: '' })
  const update = (key: string, value: string) => {
    setFields((previous) => ({ ...previous, [key]: value }))
    setError('')
  }
  const submit = (draft: boolean) => {
    const payload: Record<string, unknown> = {}
    const names = kind === 'technical_support' ? ['category', 'title', 'description', 'priority'] :
      kind === 'mentor_consultation' ? ['topic', 'description', 'preferredAt'] : ['topic', 'track', 'reason']
    for (const key of [...names, 'taskId']) {
      const value = (key === 'track' ? track : fields[key])?.trim()
      if (key === 'preferredAt' && value && !Number.isFinite(new Date(value).getTime())) {
        setError('Проверьте дату и время.'); return
      }
      if (value) payload[key] = key === 'preferredAt' ? new Date(value).toISOString() : value
    }
    if (!draft) {
      const parsed = NewRequestInputSchemas[kind].safeParse(payload)
      if (!parsed.success) { setError('Проверьте обязательные поля формы.'); return }
      if (kind === 'learning_request' && (searchedFor !== track + fields.topic?.trim() || knowledge.isPending || knowledge.isError)) {
        setError('Сначала найдите материалы по указанной теме.'); return
      }
    }
    const onError = (err: unknown) => setError(getErrorMessage(err))
    const onSuccess = (request: Request) => navigate('/requests#' + request.id)
    if (existing) {
      change.mutate({ id: existing.id, operation: 'edit', body: payload, version: existing.updatedAt }, {
        onError,
        onSuccess: (request) => {
          if (draft) onSuccess(request)
          else change.mutate({ id: existing.id, operation: 'send', version: request.updatedAt }, { onError, onSuccess })
        },
      })
      return
    }
    const body = { ...payload, saveDraft: draft }
    const fingerprint = JSON.stringify(body)
    if (attempt.current.fingerprint !== fingerprint) attempt.current = { fingerprint, key: globalThis.crypto?.randomUUID?.() ?? 'request-' + Date.now() + '-' + Math.random().toString(36).slice(2) }
    create.mutate({ kind, body, key: attempt.current.key }, { onSuccess, onError })
  }
  const short = kind === 'technical_support' ? 'title' : 'topic'
  const long = kind === 'learning_request' ? 'reason' : 'description'
  return <div className="page">
    <h1 className="heading-l">{NEW_REQUEST_LABELS[kind]}</h1>
    {kind === 'mentor_consultation' && <p className="body-secondary">Время согласуется в демо. Запись хранится в портале.</p>}
    <Card>
      <form className="stack" onSubmit={(event) => { event.preventDefault(); submit(false) }}>
        {kind === 'technical_support' && <Select label="Категория" name="category" placeholder="Выберите категорию" options={categories} value={fields.category ?? ''} onChange={(event) => update('category', event.target.value)} />}
        <Input label={short === 'title' ? 'Заголовок' : 'Тема'} name={short} value={fields[short] ?? ''} onChange={(event) => update(short, event.target.value)} maxLength={200} />
        {kind === 'learning_request' && <>
          <Select label="Направление" name="track" options={tracks} value={track} onChange={(event) => update('track', event.target.value)} />
          <Button type="button" variant="secondary" disabled={!fields.topic?.trim()} onClick={() => {
            const query = fields.topic.trim()
            setSearchedFor(track + query); setSearch(query); setError('')
          }}>Найти материалы</Button>
          {knowledge.isFetching && <p role="status">Ищем материалы…</p>}
          {knowledge.isError && <p role="alert">{getErrorMessage(knowledge.error)} <Button type="button" size="s" onClick={() => void knowledge.refetch()}>Повторить поиск</Button></p>}
          {knowledge.data?.length === 0 && <p>По этой теме материалов не найдено.</p>}
          {!!knowledge.data?.length && <KnowledgeResults hits={knowledge.data} />}
        </>}
        <Textarea name={long} label={long === 'reason' ? 'Причина запроса' : 'Описание'} rows={4} value={fields[long] ?? ''} onChange={(event) => update(long, event.target.value)} maxLength={2000} />
        {kind === 'technical_support' && <Select label="Приоритет" name="priority" options={priorities} value={fields.priority} onChange={(event) => update('priority', event.target.value)} />}
        {kind === 'mentor_consultation' && <Input label="Предпочтительная дата и время" name="preferredAt" type="datetime-local" value={fields.preferredAt} onChange={(event) => update('preferredAt', event.target.value)} />}
        <Select label="Связанная задача" name="taskId" options={[{ value: '', label: 'Без связи' }, ...(plan.data?.items ?? []).map((item) => ({ value: item.id, label: item.title }))]} value={fields.taskId ?? ''} onChange={(event) => update('taskId', event.target.value)} />
        {error && <p role="alert">{error}</p>}
        <div className="page__actions">
          <Button type="submit" loading={pending}>Отправить заявку</Button>
          <Button type="button" variant="secondary" disabled={pending} onClick={() => submit(true)}>Сохранить черновик</Button>
        </div>
      </form>
    </Card>
  </div>
}

export function PortalRequestForm() {
  const { kind, requestId } = useParams()
  const requests = useRequests()
  const parsed = NewRequestKindSchema.safeParse(kind)
  if (isMockMode) return <div className="page"><p>Для этой формы подключите сервер портала.</p></div>
  const existing = requests.data?.find((request) => request.id === requestId && request.status === 'draft' && request.allowedActions?.includes('edit'))
  const current = requestId ? NewRequestKindSchema.safeParse(existing?.kind) : parsed
  if (requestId && requests.isLoading) return <p role="status">Загружаем черновик…</p>
  if (!current.success) return <p role="alert">Форма недоступна.</p>
  return <RequestForm key={existing?.id ?? current.data} kind={current.data} existing={existing} />
}
