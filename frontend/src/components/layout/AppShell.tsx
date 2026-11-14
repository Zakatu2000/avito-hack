import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useMe } from '../../api/hooks'
import { Button } from '../ui/Button'
import { useAuthStore } from '../../stores/auth'
import { useThemeStore } from '../../stores/theme'
import { useState } from 'react'
import { BottomSheet } from '../ui/Overlay'
import { useIsMobile } from '../../hooks/useMediaQuery'
import { toast } from '../ui/Toast'
import { getErrorMessage } from '../../api/client'

export interface NavItem {
  to: string
  label: string
  icon: string
  roles?: ('intern' | 'mentor' | 'lead')[]
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Главная', icon: '🏠' },
  { to: '/timeline', label: 'Путь адаптации', icon: '🗺' },
  { to: '/chat', label: 'AI-buddy чат', icon: '💬' },
  { to: '/requests', label: 'Мои запросы', icon: '📋' },
  { to: '/contacts', label: 'К кому обратиться', icon: '🤝' },
  { to: '/kb', label: 'База знаний', icon: '📚' },
  { to: '/team', label: 'Команда', icon: '👥', roles: ['mentor', 'lead'] },
  { to: '/metrics', label: 'Метрики', icon: '📈' },
]

const MOBILE_PRIMARY = ['/', '/timeline', '/chat', '/requests']

function VisibleNav({ items }: { items: NavItem[] }) {
  const me = useMe()
  const role = me.data?.role
  return (
    <>
      {items
        .filter((item) => !item.roles || (role && item.roles.includes(role)))
        .map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => `nav__link${isActive ? ' nav__link--active' : ''}`}
          >
            <span className="nav__icon" aria-hidden="true">
              {item.icon}
            </span>
            {item.label}
          </NavLink>
        ))}
    </>
  )
}

function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme)
  const toggleTheme = useThemeStore((s) => s.toggleTheme)
  return (
    <button
      type="button"
      className="icon-btn"
      onClick={toggleTheme}
      aria-label={theme === 'light' ? 'Включить тёмную тему' : 'Включить светлую тему'}
      title={theme === 'light' ? 'Тёмная тема' : 'Светлая тема'}
    >
      {theme === 'light' ? '🌙' : '☀️'}
    </button>
  )
}

function UserChip({ compact }: { compact?: boolean }) {
  const me = useMe()
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const user = me.data
  if (!user) return null
  return (
    <div className="user-chip" data-compact={compact || undefined}>
      <div className="user-chip__avatar" aria-hidden="true">
        {user.initials}
      </div>
      {!compact && (
        <div className="user-chip__body">
          <span className="user-chip__name">{user.name}</span>
          <span className="user-chip__role">{user.roleLabel}</span>
        </div>
      )}
      <Button
        size="s"
        variant="ghost"
        style={{ marginLeft: 'auto' }}
        onClick={() => {
          void logout().then(() => navigate('/login')).catch((error: unknown) => {
            toast(getErrorMessage(error, 'Не удалось выйти. Повторите попытку'), 'error')
          })
        }}
      >
        Выйти
      </Button>
    </div>
  )
}

function MoreSheet({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const me = useMe()
  const role = me.data?.role
  const rest = NAV_ITEMS.filter((i) => !MOBILE_PRIMARY.includes(i.to)).filter(
    (item) => !item.roles || (role && item.roles.includes(role)),
  )
  return (
    <BottomSheet open={open} title="Ещё" onClose={onClose}>
      <nav className="nav" aria-label="Дополнительные разделы">
        {rest.map((item) => (
          <NavLink key={item.to} to={item.to} className="nav__link" onClick={onClose}>
            <span className="nav__icon" aria-hidden="true">
              {item.icon}
            </span>
            {item.label}
          </NavLink>
        ))}
        <NavLink to="/design" className="nav__link" onClick={onClose}>
          <span className="nav__icon" aria-hidden="true">
            🎨
          </span>
          Дизайн-система
        </NavLink>
      </nav>
    </BottomSheet>
  )
}

export function AppShell() {
  const isMobile = useIsMobile()
  const [moreOpen, setMoreOpen] = useState(false)

  return (
    <div className="shell">
      <aside className="shell__sidebar" aria-label="Основная навигация">
        <div className="wordmark">
          <span className="wordmark__top">
            Avito Start · <em>AI-buddy</em>
          </span>
          <span className="wordmark__bottom">наставник для стажёров · прототип</span>
        </div>
        <nav className="nav">
          <VisibleNav items={NAV_ITEMS} />
        </nav>
        <div className="shell__sidebar-footer">
          <UserChip />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <ThemeToggle />
            <NavLink to="/design" className="caption" style={{ fontWeight: 700 }}>
              🎨 Дизайн-система
            </NavLink>
          </div>
        </div>
      </aside>

      <div className="shell__main">
        <header className="shell__topbar">
          <div className="wordmark" style={{ display: isMobile ? 'flex' : 'none' }}>
            <span className="wordmark__top">
              Avito Start · <em>AI-buddy</em>
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginLeft: 'auto' }}>
            {isMobile && <ThemeToggle />}
            {!isMobile && <span className="caption">тестовые данные · не продукт Авито</span>}
          </div>
        </header>
        <main className="shell__content" id="content">
          <Outlet />
        </main>
      </div>

      {isMobile && (
        <nav className="mobile-nav" aria-label="Мобильная навигация">
          <ul className="mobile-nav__list">
            {NAV_ITEMS.filter((i) => MOBILE_PRIMARY.includes(i.to)).map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) => `mobile-nav__link${isActive ? ' mobile-nav__link--active' : ''}`}
                >
                  <span className="mobile-nav__icon" aria-hidden="true">
                    {item.icon}
                  </span>
                  {item.label.split(' ')[0]}
                </NavLink>
              </li>
            ))}
            <li>
              <button
                type="button"
                className="mobile-nav__link"
                onClick={() => setMoreOpen(true)}
                aria-label="Ещё разделы"
              >
                <span className="mobile-nav__icon" aria-hidden="true">
                  ⋯
                </span>
                Ещё
              </button>
            </li>
          </ul>
        </nav>
      )}
      <MoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} />
    </div>
  )
}
