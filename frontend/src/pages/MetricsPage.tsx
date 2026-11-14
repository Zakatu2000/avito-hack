import { useAdaptationMetrics } from '../api/adaptation'
import { isMockMode } from '../api/auth'
import { useMetrics } from '../api/hooks'
import { Card } from '../components/ui/Card'
import { SkeletonCard } from '../components/ui/Skeleton'
import { ErrorState } from '../components/ui/States'

const METRICS = [
  ['firstTaskMinutes', 'Время до подтверждённого старта', 'мин'],
  ['blockerMinutes', 'Время до снятия блокировки', 'мин'],
  ['requestMinutes', 'Время от отправки заявки до результата', 'мин'],
  ['withoutMentor', 'Вопросы, решённые без наставника', '%'],
  ['quickStart', 'Прогресс быстрого старта', '%'],
  ['manualActionsAvoided', 'Автоматически выполненные ручные действия', ''],
] as const

function PortalMetricsPage() {
  const metrics = useAdaptationMetrics()
  if (metrics.isPending) return <div className="page"><SkeletonCard lines={5} /></div>
  if (!metrics.data) return <ErrorState onRetry={() => void metrics.refetch()} retryLoading={metrics.isRefetching} />
  const data = metrics.data
  return <div className="page">
    <h1 className="heading-l">Метрики адаптации</h1>
    <p className="body-secondary">Измерения по событиям этой среды</p>
    <div className="grid-2">{METRICS.map(([key, label, unit]) => {
      const { value, sampleSize } = data[key]
      return <Card key={key}><h2 className="heading-s">{label}</h2>
        <p className="metric__value">{value === null ? 'Недостаточно данных' :
          (unit === '%' ? Math.round(value * 100) : value) + (unit ? ' ' + unit : '')}</p>
        {sampleSize > 0 && <p className="caption">Наблюдений: {sampleSize}</p>}
      </Card>
    })}</div>
  </div>
}

export function MetricsPage() {
  return isMockMode ? <MockMetricsPage /> : <PortalMetricsPage />
}

function MockMetricsPage() {
  const metrics = useMetrics()

  if (metrics.isLoading) {
    return (
      <div className="page">
        <SkeletonCard lines={4} />
        <SkeletonCard lines={4} />
      </div>
    )
  }
  if (metrics.isError || !metrics.data) {
    return <ErrorState onRetry={() => void metrics.refetch()} retryLoading={metrics.isRefetching} />
  }

  const m = metrics.data
  const hoursMax = m.mentorHoursSaved.target.max

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="heading-l">
            Метрики: <span className="hl hl-purple">макет</span>
          </h1>
          <p className="body-secondary" style={{ marginTop: 4 }}>
            Моковые данные для демонстрации ценности AI-buddy
          </p>
        </div>
      </div>

      <div className="grid-2">
        <Card>
          <div className="metric">
            <span className="metric__label">Часы наставника, сэкономленные за адаптацию</span>
            <span className="metric__value">
              {m.mentorHoursSaved.current} ч
            </span>
            <div
              className="metric__bar"
              role="img"
              aria-label={`Базовый уровень ${m.mentorHoursSaved.baseline.min}—${m.mentorHoursSaved.baseline.max} часов, цель ${m.mentorHoursSaved.target.min}—${m.mentorHoursSaved.target.max} часов, сейчас ${m.mentorHoursSaved.current}`}
            >
              <div
                className="metric__bar-fill metric__bar-fill--blue"
                style={{
                  left: `${(m.mentorHoursSaved.baseline.min / hoursMax) * 100}%`,
                  right: `${100 - (m.mentorHoursSaved.baseline.max / hoursMax) * 100}%`,
                }}
              />
              <div
                className="metric__bar-fill metric__bar-fill--green"
                style={{
                  left: `${(m.mentorHoursSaved.target.min / hoursMax) * 100}%`,
                  right: `${100 - (m.mentorHoursSaved.target.max / hoursMax) * 100}%`,
                }}
              />
            </div>
            <p className="caption">
              База: {m.mentorHoursSaved.baseline.min}–{m.mentorHoursSaved.baseline.max} ч (голубой) ·
              Цель: {m.mentorHoursSaved.target.min}–{m.mentorHoursSaved.target.max} ч (зелёный)
            </p>
          </div>
        </Card>

        <Card>
          <div className="metric">
            <span className="metric__label">Вопросы, решённые без наставника</span>
            <span className="metric__value">{Math.round(m.questionsWithoutMentorShare * 100)}%</span>
            <div
              className="metric__bar"
              role="img"
              aria-label={`Доля вопросов без наставника ${Math.round(m.questionsWithoutMentorShare * 100)} процентов`}
            >
              <div
                className="metric__bar-fill metric__bar-fill--green"
                style={{ width: `${m.questionsWithoutMentorShare * 100}%` }}
              />
            </div>
            <p className="caption">Бот закрыл типовые вопросы: доступы, отгулы, план</p>
          </div>
        </Card>

        <Card>
          <div className="metric">
            <span className="metric__label">Время до первой задачи</span>
            <span className="metric__value">{m.timeToFirstTaskDays.current} дн</span>
            <div
              className="metric__bar"
              role="img"
              aria-label={`Время до первой задачи: было ${m.timeToFirstTaskDays.before} дней, стало ${m.timeToFirstTaskDays.current}`}
            >
              <div
                className="metric__bar-fill metric__bar-fill--blue"
                style={{ width: `${(m.timeToFirstTaskDays.current / m.timeToFirstTaskDays.before) * 100}%` }}
              />
            </div>
            <p className="caption">Было {m.timeToFirstTaskDays.before} дн — стало {m.timeToFirstTaskDays.current} дн</p>
          </div>
        </Card>

        <Card>
          <div className="metric">
            <span className="metric__label">Стажёры в графике адаптации</span>
            <span className="metric__value">{Math.round(m.internsOnTrackShare * 100)}%</span>
            <div
              className="metric__bar"
              role="img"
              aria-label={`В графике ${Math.round(m.internsOnTrackShare * 100)} процентов стажёров`}
            >
              <div
                className="metric__bar-fill metric__bar-fill--purple"
                style={{ width: `${m.internsOnTrackShare * 100}%` }}
              />
            </div>
            <p className="caption">Не выбиваются из этапов 1 неделя → 3 месяца</p>
          </div>
        </Card>
      </div>

      <p className="caption">Макет на моковых данных — не реальные метрики Авито.</p>
    </div>
  )
}
