import { useState } from 'react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { DatePicker } from '../components/ui/DatePicker'
import { EmptyState } from '../components/ui/EmptyState'
import { Input, Textarea } from '../components/ui/Input'
import { ListItem } from '../components/ui/ListItem'
import { BottomSheet, Modal } from '../components/ui/Overlay'
import { ProgressBar } from '../components/ui/ProgressBar'
import { Select } from '../components/ui/Select'
import { Skeleton, SkeletonCard } from '../components/ui/Skeleton'
import { StatusBadge } from '../components/ui/StatusBadge'
import { Timeline } from '../components/ui/Timeline'
import { toast } from '../components/ui/Toast'
import { useIsMobile } from '../hooks/useMediaQuery'

const PALETTE: { group: string; steps: [string, string][] }[] = [
  {
    group: 'green',
    steps: [
      ['green-50', '#e6fdec'],
      ['green-100', '#c9ffc0'],
      ['green-200', '#9df5ae'],
      ['green-300', '#5ce87f'],
      ['green-400', '#04e061'],
      ['green-500', '#00c855'],
      ['green-600', '#00b94f'],
      ['green-700', '#008f3e'],
    ],
  },
  {
    group: 'blue',
    steps: [
      ['blue-50', '#e5f5ff'],
      ['blue-100', '#b8daff'],
      ['blue-200', '#8ccdff'],
      ['blue-300', '#54bfff'],
      ['blue-400', '#00aaff'],
      ['blue-500', '#0095e5'],
      ['blue-600', '#007dc2'],
      ['blue-700', '#005c8c'],
    ],
  },
  {
    group: 'purple',
    steps: [
      ['purple-50', '#f2ebfd'],
      ['purple-100', '#ddccf5'],
      ['purple-200', '#c5a9f3'],
      ['purple-300', '#b087ee'],
      ['purple-400', '#965eeb'],
      ['purple-500', '#8247d8'],
      ['purple-600', '#6e38bc'],
      ['purple-700', '#4e2782'],
    ],
  },
  {
    group: 'red',
    steps: [
      ['red-50', '#ffe9ec'],
      ['red-100', '#ffcdd3'],
      ['red-200', '#ffa3ad'],
      ['red-300', '#ff7283'],
      ['red-400', '#ff4053'],
      ['red-500', '#e52b41'],
      ['red-600', '#c21e33'],
      ['red-700', '#8f1626'],
    ],
  },
  {
    group: 'gray',
    steps: [
      ['gray-50', '#f5f5f5'],
      ['gray-100', '#ebebeb'],
      ['gray-200', '#d9d9d9'],
      ['gray-300', '#bfbfbf'],
      ['gray-400', '#999999'],
      ['gray-500', '#7a7a7a'],
      ['gray-600', '#5c5c5c'],
      ['gray-700', '#3d3d3d'],
      ['gray-800', '#1a1a1a'],
      ['gray-900', '#0a0a0a'],
    ],
  },
]

const ITEM_STATUSES = ['not_started', 'in_progress', 'pending_approval', 'done'] as const
const REQUEST_STATUSES = ['draft', 'sent', 'approving', 'approved', 'rejected'] as const

export function DesignPage() {
  const isMobile = useIsMobile()
  const [modalOpen, setModalOpen] = useState(false)
  const [sheetOpen, setSheetOpen] = useState(false)

  return (
    <main style={{ maxWidth: 1080, margin: '0 auto', padding: '32px 24px 96px', display: 'flex', flexDirection: 'column', gap: 40 }}>
      <header>
        <p className="caption" style={{ marginBottom: 8 }}>
          Avito Start · AI-buddy · витрина дизайн-системы
        </p>
        <h1 className="heading-xl">
          Дизайн-система: <span className="hl hl-green">токены</span> и компоненты
        </h1>
        <p className="body-secondary" style={{ marginTop: 12, maxWidth: 640 }}>
          Все цвета и текстовые стили — из tokens.css. Компоненты показаны во всех состояниях:
          default, hover, focus, disabled, loading, error.
        </p>
      </header>

      <section className="demo-block" aria-label="Палитра">
        <h2 className="heading-m">Палитра</h2>
        {PALETTE.map((group) => (
          <div key={group.group} style={{ marginBottom: 16 }}>
            <p className="demo-label" style={{ margin: '12px 0 8px' }}>
              {group.group}
            </p>
            <div className="swatches">
              {group.steps.map(([name, hex]) => (
                <div className="swatch" key={name}>
                  <div className="swatch__color" style={{ background: `var(--${name})` }} />
                  <div className="swatch__name">{name}</div>
                  <div className="swatch__hex">{hex}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </section>

      <section className="demo-block" aria-label="Типографика">
        <h2 className="heading-m">Типографика</h2>
        <p className="heading-xl">
          Heading XL — <span className="hl hl-blue">крупные</span> плотные заголовки
        </p>
        <p className="heading-l">Heading L — заголовок страницы</p>
        <p className="heading-m">Heading M — заголовок секции</p>
        <p className="heading-s">Heading S — заголовок карточки</p>
        <p className="body">Body — спокойный основной текст про адаптацию стажёров.</p>
        <p className="caption">Caption — подписи и подсказки</p>
      </section>

      <section className="demo-block" aria-label="Кнопки">
        <h2 className="heading-m">Button</h2>
        <div className="demo-row">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button loading>Loading</Button>
          <Button disabled>Disabled</Button>
          <Button size="s">Small</Button>
          <Button size="l">Large</Button>
        </div>
      </section>

      <section className="demo-block" aria-label="Поля ввода">
        <h2 className="heading-m">Input · Select · DatePicker · Textarea</h2>
        <div className="grid-2">
          <Input label="Обычное поле" placeholder="Например, Аня" name="demo-input" />
          <Input label="Поле с ошибкой" defaultValue="ab" error="Минимум 3 символа" name="demo-input-err" />
          <Input label="Недоступно" placeholder="Недоступно" disabled name="demo-input-dis" />
          <Select
            label="Селект"
            placeholder="Выбери значение"
            name="demo-select"
            options={[
              { value: '1', label: 'Один' },
              { value: '2', label: 'Два' },
            ]}
          />
          <DatePicker label="Дата" name="demo-date" />
          <Textarea label="Комментарий" placeholder="Пара слов" name="demo-text" rows={3} />
        </div>
      </section>

      <section className="demo-block" aria-label="Карточки">
        <h2 className="heading-m">Card · пастельные тона</h2>
        <div className="grid-4">
          <Card tone="green">
            <p className="heading-s">Зелёная</p>
            <p className="body">Готово</p>
          </Card>
          <Card tone="blue">
            <p className="heading-s">Голубая</p>
            <p className="body">В процессе</p>
          </Card>
          <Card tone="purple">
            <p className="heading-s">Сиреневая</p>
            <p className="body">Ждёт согласования</p>
          </Card>
          <Card tone="gray">
            <p className="heading-s">Серая</p>
            <p className="body">Не начато</p>
          </Card>
        </div>
      </section>

      <section className="demo-block" aria-label="Статусы">
        <h2 className="heading-m">StatusBadge</h2>
        <div className="demo-row">
          {ITEM_STATUSES.map((s) => (
            <StatusBadge key={s} status={s} />
          ))}
          {REQUEST_STATUSES.map((s) => (
            <StatusBadge key={s} status={s} />
          ))}
          <StatusBadge status="approved" label="Выдан" />
        </div>
      </section>

      <section className="demo-block" aria-label="ListItem и прогресс">
        <h2 className="heading-m">ListItem · ProgressBar</h2>
        <ListItem
          icon="💬"
          title="Чаты и каналы"
          subtitle="Вступи в #team-interns и напиши приветствие"
          right={<StatusBadge status="done" />}
        />
        <ProgressBar value={62} label="Прогресс адаптации" />
      </section>

      <section className="demo-block" aria-label="Timeline">
        <h2 className="heading-m">Timeline</h2>
        <Timeline
          ariaLabel="Пример таймлайна"
          stages={[
            {
              id: 's1',
              title: '1-я неделя',
              caption: '4 из 4 готово',
              tone: 'green',
              content: (
                <ListItem icon="✅" title="Все пункты закрыты" subtitle="Отличный старт" />
              ),
            },
            {
              id: 's2',
              title: '2-я неделя',
              caption: '1 из 3 в процессе',
              tone: 'blue',
              content: (
                <>
                  <ListItem icon="🛠" title="Первая задача" subtitle="Возьми тикет в Jira" right={<StatusBadge status="in_progress" />} />
                  <ListItem icon="📚" title="Мануалы" subtitle="Прочитай README команды" right={<StatusBadge status="not_started" />} />
                </>
              ),
            },
          ]}
        />
      </section>

      <section className="demo-block" aria-label="Оверлеи и тосты">
        <h2 className="heading-m">Modal · BottomSheet · Toast</h2>
        <div className="demo-row">
          <Button variant="secondary" onClick={() => setModalOpen(true)}>
            Открыть Modal
          </Button>
          <Button variant="secondary" onClick={() => setSheetOpen(true)}>
            Открыть BottomSheet
          </Button>
          <Button variant="ghost" onClick={() => toast('Запрос отправлен', 'success')}>
            Toast: успех
          </Button>
          <Button variant="ghost" onClick={() => toast('Не получилось отправить', 'error')}>
            Toast: ошибка
          </Button>
        </div>
        <p className="caption">На этом экране используется вариант: {isMobile ? 'BottomSheet' : 'Modal'} (по ширине окна).</p>
        <Modal
          open={modalOpen}
          title="Превью запроса"
          onClose={() => setModalOpen(false)}
          footer={
            <>
              <Button variant="secondary" onClick={() => setModalOpen(false)}>
                Отмена
              </Button>
              <Button onClick={() => setModalOpen(false)}>Отправить</Button>
            </>
          }
        >
          <div className="preview-rows">
            <div className="preview-row">
              <span className="preview-row__key">Тип</span>
              <span className="preview-row__value">Отгул</span>
            </div>
            <div className="preview-row">
              <span className="preview-row__key">Согласуют</span>
              <span className="preview-row__value">Марина Ким → Олег Ветров</span>
            </div>
          </div>
        </Modal>
        <BottomSheet open={sheetOpen} title="Быстрые действия" onClose={() => setSheetOpen(false)}>
          <p className="body-secondary">Так выглядят действия на мобильном.</p>
        </BottomSheet>
      </section>

      <section className="demo-block" aria-label="Скелетоны и пустые состояния">
        <h2 className="heading-m">Skeleton · EmptyState</h2>
        <div className="grid-2">
          <SkeletonCard lines={3} />
          <EmptyState
            icon="📭"
            title="Запросов пока нет"
            hint="Оформи отгул или запроси доступ — они появятся здесь"
            action={<Button size="s">Оформить отгул</Button>}
          />
        </div>
        <Skeleton width={220} height={28} />
      </section>
    </main>
  )
}
