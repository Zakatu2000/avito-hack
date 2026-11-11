import { Navigate, useNavigate } from 'react-router-dom'
import { useUsers } from '../api/hooks'
import { Button } from '../components/ui/Button'
import { Skeleton } from '../components/ui/Skeleton'
import { StatusBadge } from '../components/ui/StatusBadge'
import { useAuthStore } from '../stores/auth'

const ROLE_TONE: Record<string, string> = {
  intern: 'var(--card-green)',
  mentor: 'var(--card-purple)',
  lead: 'var(--card-blue)',
}

export function LoginPage() {
  const { data: users, isLoading, error, refetch, isRefetching } = useUsers()
  const login = useAuthStore((s) => s.login)
  const currentUserId = useAuthStore((s) => s.userId)
  const navigate = useNavigate()

  if (currentUserId) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="login">
      <section className="login__hero">
        <div className="wordmark">
          <span className="wordmark__top" style={{ fontSize: 22 }}>
            Avito Start · <em>AI-buddy</em>
          </span>
          <span className="wordmark__bottom">наставник для стажёров · прототип хакатона</span>
        </div>
        <h1 className="heading-xl login__hero-title">
          Стажировка без хаоса: <span className="hl hl-green">план</span>, запросы и подсказки в одном
          месте
        </h1>
        <p className="body" style={{ maxWidth: 480 }}>
          AI-buddy ведёт стажёра по этапам адаптации, помогает оформить отгул и доступ, а наставнику
          экономит часы на рутинных вопросах.
        </p>
        <p className="caption">Все данные синтетические. Прототип — не продукт Авито.</p>
      </section>

      <section className="login__panel" aria-label="Выбор тестового пользователя">
        <div>
          <h2 className="heading-m">Войти как тестовый пользователь</h2>
          <p className="caption" style={{ marginTop: 4 }}>
            Демо-вход без пароля — просто выбери роль
          </p>
        </div>
        {isLoading &&
          Array.from({ length: 4 }, (_, i) => <Skeleton key={i} height={80} radius={20} />)}
        {error && (
          <>
            <p className="body-secondary">Не удалось загрузить пользователей.</p>
            <Button variant="secondary" onClick={() => void refetch()} loading={isRefetching}>
              Повторить
            </Button>
          </>
        )}
        {users?.map((user) => (
          <button
            key={user.id}
            type="button"
            className="login-user"
            onClick={() => {
              login(user.id)
              navigate('/', { replace: true })
            }}
          >
            <span className="login-user__avatar" style={{ background: ROLE_TONE[user.role] }} aria-hidden="true">
              {user.initials}
            </span>
            <span className="login-user__body">
              <span className="login-user__name">{user.name}</span>
              <span className="login-user__desc">
                {user.roleLabel} · {user.team}
              </span>
            </span>
            <span className="login-user__role">
              <StatusBadge
                status={user.role === 'intern' ? 'in_progress' : 'done'}
                label={user.role === 'intern' ? 'стажёр' : user.role === 'mentor' ? 'наставник' : 'руководитель'}
              />
            </span>
          </button>
        ))}
      </section>
    </div>
  )
}
