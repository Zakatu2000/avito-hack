import { useMetrics } from '../api/hooks'
import { Card } from '../components/ui/Card'
import { SkeletonCard } from '../components/ui/Skeleton'
import { ErrorState } from '../components/ui/States'

export function MetricsPage() {
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
