import { useState } from 'react'
import { Link } from 'react-router-dom'
import { usePortalRequestAction } from '../api/adaptation'
import { getErrorMessage } from '../api/client'
import type { Request, RequestOperation } from '../api/schemas'
import { Button } from './ui/Button'
import { Input, Textarea } from './ui/Input'
import { Modal } from './ui/Overlay'
import { toast } from './ui/Toast'

const labels: Record<RequestOperation, string> = {
  edit: 'Редактировать', send: 'Отправить', claim: 'Взять в работу', resolve: 'Предложить решение',
  close: 'Закрыть обращение', reopen: 'Вернуть в работу', schedule: 'Подтвердить время',
  propose: 'Предложить другое время', accept: 'Принять время', counter: 'Предложить другое время',
  complete: 'Завершить консультацию', recommend: 'Сохранить рекомендацию',
}
const withInput: RequestOperation[] = ['resolve', 'reopen', 'complete', 'recommend', 'propose', 'counter']

export function PortalRequestActions({ request }: { request: Request }) {
  const change = usePortalRequestAction()
  const [operation, setOperation] = useState<RequestOperation | null>(null)
  const [value, setValue] = useState('')
  const [link, setLink] = useState('')
  const [error, setError] = useState('')
  const time = operation === 'propose' || operation === 'counter'
  const run = (action: RequestOperation) => {
    if (time && !Number.isFinite(new Date(value).getTime())) { setError('Проверьте дату и время'); return }
    const body = !withInput.includes(action) ? undefined : time ? { at: new Date(value).toISOString() } :
      action === 'reopen' ? { comment: value } : { result: value, ...(action === 'recommend' && link.trim() ? { url: link.trim() } : {}) }
    change.mutate({ id: request.id, operation: action, body, version: request.updatedAt }, {
      onSuccess: () => { setOperation(null); toast('Запрос обновлён', 'success') },
      onError: (err) => { setError(getErrorMessage(err)); if (!operation) toast(getErrorMessage(err), 'error') },
    })
  }
  return <>
    <div className="page__actions">
      {(request.allowedActions ?? []).map((action) => {
        if (action === 'edit') return <Link key={action} className="btn btn--s btn--secondary" to={'/requests/' + request.id + '/edit'}>Редактировать и отправить</Link>
        if (action === 'send') return null
        return <Button size="s" variant="secondary" key={action} disabled={change.isPending} onClick={() => {
          setError('')
          if (!withInput.includes(action)) { run(action); return }
          setValue(''); setLink(''); setOperation(action)
        }}>{labels[action]}</Button>
      })}
    </div>
    <Modal open={!!operation} title={operation ? labels[operation] : ''} onClose={() => setOperation(null)} footer={
      <Button type="submit" form={'operation-' + request.id} loading={change.isPending} disabled={!value.trim()}>Сохранить</Button>
    }>
      <form id={'operation-' + request.id} className="stack" onSubmit={(event) => { event.preventDefault(); if (operation && value.trim()) run(operation) }}>
        {time ? <Input label="Дата и время" name="slot" type="datetime-local" value={value} onChange={(event) => setValue(event.target.value)} /> :
          <Textarea label={operation === 'reopen' ? 'Комментарий' : 'Результат'} name="result" rows={4} value={value} onChange={(event) => setValue(event.target.value)} maxLength={operation === 'reopen' ? 1000 : 2000} />}
        {operation === 'recommend' && <Input label="Ссылка на рекомендацию" name="url" type="url" value={link} onChange={(event) => setLink(event.target.value)} />}
        {error && <p role="alert">{error}</p>}
      </form>
    </Modal>
  </>
}
