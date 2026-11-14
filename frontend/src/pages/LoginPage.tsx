import { Navigate, useNavigate } from 'react-router-dom'
import { useUsers } from '../api/hooks'
import { Button } from '../components/ui/Button'
import { Skeleton } from '../components/ui/Skeleton'
import { StatusBadge } from '../components/ui/StatusBadge'
import { useAuthStore } from '../stores/auth'
import { useState, type FormEvent } from 'react'
import { Input } from '../components/ui/Input'
import { isMockMode } from '../api/auth'
import { getErrorMessage } from '../api/client'

const ROLE_TONE: Record<string, string> = {
  intern: 'var(--card-green)',
  mentor: 'var(--card-purple)',
  lead: 'var(--card-blue)',
}

function DemoLoginPage() {
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

export function LoginPage() {
  if (isMockMode) return <DemoLoginPage />
  return <PasswordLoginPage />
}

function PasswordLoginPage() {
  const [register, setRegister] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const userId = useAuthStore((s) => s.userId)
  const signIn = useAuthStore((s) => s.signIn)
  if (userId) return <Navigate to="/" replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setPending(true)
    try {
      await signIn(email.trim().toLowerCase(), password, register ? name.trim() : undefined)
    } catch (err) {
      setError(getErrorMessage(err, 'Не удалось войти. Проверьте соединение и повторите попытку'))
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="login">
      <section className="login__hero">
        <div className="wordmark">
          <span className="wordmark__top" style={{ fontSize: 22 }}>Avito Start · <em>AI-buddy</em></span>
          <span className="wordmark__bottom">наставник для стажёров · прототип хакатона</span>
        </div>
        <h1 className="heading-xl login__hero-title">Стажировка без хаоса: <span className="hl hl-green">план</span>, запросы и подсказки в одном месте</h1>
        <p className="body" style={{ maxWidth: 480 }}>AI-buddy ведёт по этапам адаптации, помогает оформить отгул и доступ, а наставнику экономит время на рутинных вопросах.</p>
        <p className="caption">Прототип — не продукт Авито.</p>
      </section>
      <section className="login__panel" aria-label={register ? 'Регистрация' : 'Вход в аккаунт'}>
        <h2 className="heading-m">{register ? 'Создать аккаунт' : 'Войти в аккаунт'}</h2>
        <form onSubmit={(event) => void submit(event)} style={{ display: 'grid', gap: 16 }}>
          {register && <Input name="name" label="Имя и фамилия" autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} required minLength={2} maxLength={100} disabled={pending} />}
          <Input name="email" label="Email" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required maxLength={254} disabled={pending} />
          <Input name="password" label="Пароль" type="password" autoComplete={register ? 'new-password' : 'current-password'} value={password} onChange={(event) => setPassword(event.target.value)} required minLength={register ? 12 : 1} maxLength={128} hint={register ? 'Минимум 12 символов' : undefined} disabled={pending} />
          {error && <p className="field__error" role="alert">{error}</p>}
          <Button type="submit" loading={pending} fullWidth>{register ? 'Зарегистрироваться' : 'Войти'}</Button>
        </form>
        <Button variant="ghost" disabled={pending} onClick={() => { setRegister(!register); setError(null); setPassword('') }}>
          {register ? 'Уже есть аккаунт? Войти' : 'Создать аккаунт'}
        </Button>
      </section>
    </div>
  )
}
