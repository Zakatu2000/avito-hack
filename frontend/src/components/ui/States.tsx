import { Link } from 'react-router-dom'
import { Button } from './Button'

export function NoAccess({
  title = 'Нет доступа',
  text = 'Эта область доступна только наставникам и руководителям. Если нужен доступ — попроси у своего руководителя.',
}: {
  title?: string
  text?: string
}) {
  return (
    <div className="state-block" role="alert">
      <div className="state-block__icon" aria-hidden="true">
        🔒
      </div>
      <h2 className="state-block__title">{title}</h2>
      <p className="state-block__text">{text}</p>
      <Link to="/">
        <Button variant="secondary">На главную</Button>
      </Link>
    </div>
  )
}

export function ErrorState({
  text = 'Что-то пошло не так при загрузке. Попробуй ещё раз.',
  onRetry,
  retryLoading,
}: {
  text?: string
  onRetry?: () => void
  retryLoading?: boolean
}) {
  return (
    <div className="state-block" role="alert">
      <div className="state-block__icon" aria-hidden="true">
        ⚠️
      </div>
      <h2 className="state-block__title">Ошибка загрузки</h2>
      <p className="state-block__text">{text}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry} loading={retryLoading}>
          Повторить
        </Button>
      )}
    </div>
  )
}
