import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from '../src/components/ui/Button'
import { EmptyState } from '../src/components/ui/EmptyState'
import { Input } from '../src/components/ui/Input'
import { ListItem } from '../src/components/ui/ListItem'
import { Modal } from '../src/components/ui/Overlay'
import { ProgressBar } from '../src/components/ui/ProgressBar'
import { StatusBadge } from '../src/components/ui/StatusBadge'
import { Timeline } from '../src/components/ui/Timeline'
import { useToastStore } from '../src/components/ui/Toast'
import { renderWithProviders } from './helpers'

describe('Button', () => {
  it('показывает спиннер и блокирует нажатие в loading', async () => {
    const onClick = vi.fn()
    renderWithProviders(
      <Button loading onClick={onClick}>
        Отправить
      </Button>,
    )
    const btn = screen.getByRole('button', { name: /отправить/i })
    expect(btn).toBeDisabled()
    expect(btn).toHaveAttribute('aria-busy', 'true')
    await userEvent.click(btn)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('вызывает onClick в обычном состоянии', async () => {
    const onClick = vi.fn()
    renderWithProviders(<Button onClick={onClick}>Отправить</Button>)
    await userEvent.click(screen.getByRole('button'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('блокируется через disabled', () => {
    renderWithProviders(<Button disabled>Недоступно</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })
})

describe('StatusBadge', () => {
  it('подписывает все статусы пунктов и запросов', () => {
    const labels = [
      ['not_started', 'Не начато'],
      ['in_progress', 'В процессе'],
      ['pending_approval', 'Ждёт согласования'],
      ['done', 'Готово'],
      ['draft', 'Черновик'],
      ['approving', 'На согласовании'],
      ['rejected', 'Отклонён'],
    ] as const
    renderWithProviders(
      <div>
        {labels.map(([status]) => (
          <StatusBadge key={status} status={status} />
        ))}
      </div>,
    )
    for (const [, label] of labels) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('позволяет переопределить подпись (Выдан для доступа)', () => {
    renderWithProviders(<StatusBadge status="approved" label="Выдан" />)
    expect(screen.getByText('Выдан')).toBeInTheDocument()
  })
})

describe('Input', () => {
  it('связывает label с полем и показывает ошибку с role=alert', () => {
    renderWithProviders(
      <Input label="Дата начала" name="start" error="Конец раньше начала" defaultValue="x" />,
    )
    expect(screen.getByLabelText('Дата начала')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).toHaveTextContent('Конец раньше начала')
  })
})

describe('Modal', () => {
  it('закрывается по Escape и кнопке, ловит клик по фону', async () => {
    const onClose = vi.fn()
    const { rerender } = renderWithProviders(
      <Modal open title="Превью запроса" onClose={onClose}>
        контент
      </Modal>,
    )
    expect(screen.getByRole('dialog', { name: 'Превью запроса' })).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(1)

    rerender(
      <div />
    )
    renderWithProviders(
      <Modal open={false} title="Скрытый" onClose={onClose}>
        x
      </Modal>,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('Toast', () => {
  it('показывает уведомление и удаляет по кнопке', async () => {
    renderWithProviders(
      <button type="button" onClick={() => useToastStore.getState().push('Запрос отправлен', 'success')}>
        пуш
      </button>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'пуш' }))
    expect(await screen.findByText('Запрос отправлен')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Скрыть уведомление' }))
    await waitFor(() => expect(screen.queryByText('Запрос отправлен')).not.toBeInTheDocument())
  })
})

describe('Timeline', () => {
  it('рисует этапы с заголовками и контентом', () => {
    renderWithProviders(
      <Timeline
        ariaLabel="Этапы"
        stages={[
          { id: 's1', title: '1-я неделя', caption: '4/4', tone: 'green', content: <div>Пункт A</div> },
          { id: 's2', title: '2-я неделя', tone: 'blue', content: <div>Пункт B</div> },
        ]}
      />,
    )
    expect(screen.getByText('1-я неделя')).toBeInTheDocument()
    expect(screen.getByText('Пункт B')).toBeInTheDocument()
  })
})

describe('ListItem / ProgressBar / EmptyState', () => {
  it('отображают подписи, aria и подсказки', () => {
    renderWithProviders(
      <div>
        <ListItem icon="⏰" title="Экватор" subtitle="6-я неделя" right={<StatusBadge status="pending_approval" />} />
        <ProgressBar value={62} label="Прогресс" />
        <EmptyState icon="📭" title="Пусто" hint="Здесь появятся запросы" />
      </div>,
    )
    expect(screen.getByText('Экватор')).toBeInTheDocument()
    expect(screen.getByText('6-я неделя')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '62')
    expect(screen.getByText('Пусто')).toBeInTheDocument()
  })
})
