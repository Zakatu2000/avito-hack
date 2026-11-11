import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getErrorMessage } from '../api/client'
import { useCreateLeaveRequest } from '../api/hooks'
import { LeaveRequestInputSchema, type LeaveRequestInput, type LeaveReason } from '../api/schemas'
import { Button } from '../components/ui/Button'
import { DatePicker } from '../components/ui/DatePicker'
import { Textarea } from '../components/ui/Input'
import { BottomSheet, Modal } from '../components/ui/Overlay'
import { Select } from '../components/ui/Select'
import { toast } from '../components/ui/Toast'
import { useIsMobile } from '../hooks/useMediaQuery'
import { LEAVE_REASON_LABELS, formatDateRu } from '../utils/requestView'

const REASON_OPTIONS = (Object.keys(LEAVE_REASON_LABELS) as LeaveReason[]).map((value) => ({
  value,
  label: LEAVE_REASON_LABELS[value],
}))

function todayISO(): string {
  return new Date().toISOString().slice(0, 10)
}

export function LeaveFormPage() {
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [reason, setReason] = useState('')
  const [comment, setComment] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [previewOpen, setPreviewOpen] = useState(false)
  const create = useCreateLeaveRequest()
  const navigate = useNavigate()
  const isMobile = useIsMobile()

  const input: LeaveRequestInput = {
    startDate,
    endDate,
    reason: (reason || 'other') as LeaveReason,
    comment: comment || undefined,
  }

  const validate = (): boolean => {
    const parsed = LeaveRequestInputSchema.safeParse(input)
    if (parsed.success && endDate < startDate) {
      setErrors({ endDate: 'Конец не может быть раньше начала' })
      return false
    }
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
      { ...input, reason: input.reason as LeaveReason, saveDraft },
      {
        onSuccess: (request) => {
          toast(saveDraft ? 'Черновик сохранён' : 'Запрос отправлен наставнику и руководителю', 'success')
          navigate('/requests')
          void request.id
        },
        onError: (err) => toast(getErrorMessage(err), 'error'),
      },
    )
  }

  const PreviewBody = (
    <div className="preview-rows">
      <div className="preview-row">
        <span className="preview-row__key">Тип</span>
        <span className="preview-row__value">Отгул</span>
      </div>
      <div className="preview-row">
        <span className="preview-row__key">Даты</span>
        <span className="preview-row__value">
          {formatDateRu(startDate)} — {formatDateRu(endDate)}
        </span>
      </div>
      <div className="preview-row">
        <span className="preview-row__key">Причина</span>
        <span className="preview-row__value">{LEAVE_REASON_LABELS[input.reason]}</span>
      </div>
      {comment && (
        <div className="preview-row">
          <span className="preview-row__key">Комментарий</span>
          <span className="preview-row__value">{comment}</span>
        </div>
      )}
      <div className="preview-row">
        <span className="preview-row__key">Согласуют</span>
        <span className="preview-row__value">Марина Ким (наставница) → Олег Ветров (руководитель)</span>
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
          <h1 className="heading-l">Оформить отгул</h1>
          <p className="body-secondary" style={{ marginTop: 4 }}>
            Имитация системы отсутствий: запрос, превью, статусы
          </p>
        </div>
      </div>

      <form
        className="stack"
        style={{ maxWidth: 560 }}
        onSubmit={(e) => {
          e.preventDefault()
          if (validate()) setPreviewOpen(true)
        }}
      >
        <div className="grid-2">
          <DatePicker
            label="Дата начала"
            name="leave-start"
            min={todayISO()}
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            error={errors.startDate}
          />
          <DatePicker
            label="Дата окончания"
            name="leave-end"
            min={startDate || todayISO()}
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            error={errors.endDate}
          />
        </div>
        <Select
          label="Причина"
          name="leave-reason"
          placeholder="Выбери причину"
          options={REASON_OPTIONS}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          error={errors.reason}
        />
        <Textarea
          label="Комментарий (необязательно)"
          name="leave-comment"
          rows={3}
          placeholder="Пара слов для согласующих"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          error={errors.comment}
          hint="До 300 символов"
        />
        <div style={{ display: 'flex', gap: 8 }}>
          <Button type="submit">Предпросмотр и отправка</Button>
          <Button variant="ghost" onClick={() => navigate('/requests')}>
            Отмена
          </Button>
        </div>
      </form>

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
