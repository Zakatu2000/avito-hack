import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getErrorMessage } from '../api/client'
import { useAccessSystems, useCreateAccessRequest } from '../api/hooks'
import { AccessRequestInputSchema, type AccessRequestInput } from '../api/schemas'
import { Button } from '../components/ui/Button'
import { Textarea } from '../components/ui/Input'
import { BottomSheet, Modal } from '../components/ui/Overlay'
import { Select } from '../components/ui/Select'
import { Skeleton } from '../components/ui/Skeleton'
import { toast } from '../components/ui/Toast'
import { useIsMobile } from '../hooks/useMediaQuery'

const DURATION_OPTIONS = [
  { value: '30', label: '30 дней' },
  { value: '90', label: '90 дней' },
  { value: '180', label: '180 дней' },
  { value: '365', label: 'Год' },
]

export function AccessFormPage() {
  const systems = useAccessSystems()
  const [params] = useSearchParams()
  const [systemId, setSystemId] = useState(params.get('system') ?? '')
  const [justification, setJustification] = useState('')
  const [durationDays, setDurationDays] = useState('90')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [previewOpen, setPreviewOpen] = useState(false)
  const create = useCreateAccessRequest()
  const navigate = useNavigate()
  const isMobile = useIsMobile()

  const system = systems.data?.find((s) => s.id === systemId)

  useEffect(() => {
    if (system && !DURATION_OPTIONS.some((o) => o.value === String(system.defaultDurationDays))) return
    if (system) setDurationDays(String(system.defaultDurationDays))
  }, [system])

  const input: AccessRequestInput = {
    system: systemId,
    justification,
    durationDays: Number(durationDays),
    taskId: params.get('task') || undefined,
  }

  const validate = (): boolean => {
    const parsed = AccessRequestInputSchema.safeParse(input)
    if (parsed.success) {
      setErrors({})
      return true
    }
    const fieldErrors: Record<string, string> = {}
    for (const issue of parsed.error.issues) {
      const key = String(issue.path[0])
      if (!fieldErrors[key]) fieldErrors[key] = issue.message
    }
    setErrors(fieldErrors)
    return false
  }

  const submit = (saveDraft: boolean) => {
    create.mutate(
      { ...input, saveDraft },
      {
        onSuccess: () => {
          toast(saveDraft ? 'Черновик сохранён' : 'Запрос ушёл руководителю', 'success')
          navigate('/requests')
        },
        onError: (err) => toast(getErrorMessage(err), 'error'),
      },
    )
  }

  const PreviewBody = (
    <div className="preview-rows">
      <div className="preview-row">
        <span className="preview-row__key">Система</span>
        <span className="preview-row__value">{system?.name ?? systemId}</span>
      </div>
      <div className="preview-row">
        <span className="preview-row__key">Обоснование</span>
        <span className="preview-row__value" style={{ maxWidth: 320, whiteSpace: 'normal' }}>
          {justification}
        </span>
      </div>
      <div className="preview-row">
        <span className="preview-row__key">Срок доступа</span>
        <span className="preview-row__value">{durationDays} дней</span>
      </div>
      <div className="preview-row">
        <span className="preview-row__key">Согласует</span>
        <span className="preview-row__value">Олег Ветров (руководитель)</span>
      </div>
      <div className="preview-row">
        <span className="preview-row__key">Статусная цепочка</span>
        <span className="preview-row__value">отправлен → на согласовании → выдан / отклонён</span>
      </div>
    </div>
  )

  const PreviewFooter = (
    <>
      <Button variant="secondary" onClick={() => submit(true)} disabled={create.isPending}>
        Сохранить черновик
      </Button>
      <Button loading={create.isPending} onClick={() => submit(false)}>
        Отправить
      </Button>
    </>
  )

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="heading-l">Запросить доступ</h1>
          <p className="body-secondary" style={{ marginTop: 4 }}>
            Заявка уйдёт руководителю: отправлен → на согласовании → выдан или отклонён
          </p>
        </div>
      </div>

      {systems.isLoading && <Skeleton height={160} radius={20} />}
      {systems.data && (
        <form
          className="stack"
          style={{ maxWidth: 560 }}
          onSubmit={(e) => {
            e.preventDefault()
            if (validate()) setPreviewOpen(true)
          }}
        >
          <Select
            label="Система"
            name="access-system"
            placeholder="Выбери систему"
            options={systems.data.map((s) => ({ value: s.id, label: s.name }))}
            value={systemId}
            onChange={(e) => setSystemId(e.target.value)}
            error={errors.system}
            hint={system?.description}
          />
          <Textarea
            label="Для какой задачи нужен доступ"
            name="access-justification"
            rows={3}
            placeholder="Например: нужен Jira, чтобы брать задачи из спринта стажёров"
            value={justification}
            onChange={(e) => setJustification(e.target.value)}
            error={errors.justification}
            hint="Минимум 10 символов — так согласующему проще решить"
          />
          <Select
            label="Срок"
            name="access-duration"
            options={DURATION_OPTIONS}
            value={durationDays}
            onChange={(e) => setDurationDays(e.target.value)}
            error={errors.durationDays}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <Button type="submit">Предпросмотр и отправка</Button>
            <Button variant="ghost" onClick={() => navigate('/requests')}>
              Отмена
            </Button>
          </div>
        </form>
      )}

      {isMobile ? (
        <BottomSheet open={previewOpen} title="Проверь запрос" onClose={() => setPreviewOpen(false)} footer={PreviewFooter}>
          {PreviewBody}
        </BottomSheet>
      ) : (
        <Modal open={previewOpen} title="Проверь запрос" onClose={() => setPreviewOpen(false)} footer={PreviewFooter}>
          {PreviewBody}
        </Modal>
      )}
    </div>
  )
}
