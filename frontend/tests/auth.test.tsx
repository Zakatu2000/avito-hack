import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from './setup'
import { renderWithProviders } from './helpers'
import { LoginPage } from '../src/pages/LoginPage'
import { useAuthStore } from '../src/stores/auth'
import { apiFetch } from '../src/api/client'
import { UserSchema } from '../src/api/schemas'

vi.mock('../src/api/auth', async (original) => ({
  ...await original<typeof import('../src/api/auth')>(),
  isMockMode: false,
}))
vi.mock('../src/stores/auth', async (original) => {
  const module = await original<typeof import('../src/stores/auth')>()
  return { ...module, useAuthStore: module.createAuthStore(false) }
})

const user = { id: 'real-intern', name: 'Анна Тест', role: 'intern', roleLabel: 'Стажёр', team: 'Platform Interns', initials: 'АТ' }

beforeEach(() => {
  useAuthStore.setState({ userId: null, csrfToken: null, ready: true, error: null })
  localStorage.clear()
})

describe('Вход и серверная сессия', () => {
  it('показывает парольную форму и ошибку неверного пароля', async () => {
    server.use(http.post('*/api/auth/login', () => HttpResponse.json({ message: 'Неверный email или пароль' }, { status: 401 })))
    renderWithProviders(<LoginPage />)
    expect(screen.queryByText('Аня Петрова')).not.toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Email'), 'anna@example.test')
    await userEvent.type(screen.getByLabelText('Пароль'), 'wrong-password')
    await userEvent.click(screen.getByRole('button', { name: 'Войти' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Неверный email или пароль')
    expect(useAuthStore.getState().userId).toBeNull()
  })

  it('регистрирует только имя, email и пароль и сохраняет CSRF в памяти', async () => {
    let submitted: unknown
    server.use(http.post('*/api/auth/register', async ({ request }) => {
      submitted = await request.json()
      return HttpResponse.json({ user, csrfToken: 'test-csrf' }, { status: 201 })
    }))
    renderWithProviders(<LoginPage />)
    await userEvent.click(screen.getByRole('button', { name: 'Создать аккаунт' }))
    await userEvent.type(screen.getByLabelText('Имя и фамилия'), 'Анна Тест')
    await userEvent.type(screen.getByLabelText('Email'), 'anna@example.test')
    await userEvent.type(screen.getByLabelText('Пароль'), 'long-password-123')
    await userEvent.click(screen.getByRole('button', { name: 'Зарегистрироваться' }))
    await waitFor(() => expect(useAuthStore.getState().userId).toBe(user.id))
    expect(submitted).toEqual({ name: 'Анна Тест', email: 'anna@example.test', password: 'long-password-123' })
    expect(useAuthStore.getState().csrfToken).toBe('test-csrf')
    expect(localStorage.getItem('ai-buddy-auth')).toBeNull()
  })

  it('восстанавливает сессию и завершает её на сервере при выходе', async () => {
    let logoutCsrf: string | null = null
    server.use(
      http.get('*/api/auth/session', () => HttpResponse.json({ user, csrfToken: 'restored-token' })),
      http.post('*/api/auth/logout', ({ request }) => {
        logoutCsrf = request.headers.get('X-CSRF-Token')
        return HttpResponse.json({ loggedOut: true })
      }),
    )
    await useAuthStore.getState().initialize()
    expect(useAuthStore.getState()).toMatchObject({ userId: user.id, csrfToken: 'restored-token', ready: true })
    await useAuthStore.getState().logout()
    expect(logoutCsrf).toBe('restored-token')
    expect(useAuthStore.getState().userId).toBeNull()
  })

  it('передаёт CSRF вместо x-user-id и сбрасывает истёкшую сессию', async () => {
    let identity: string | null = null
    let csrf: string | null = null
    server.use(http.post('*/api/me', ({ request }) => {
      identity = request.headers.get('x-user-id')
      csrf = request.headers.get('X-CSRF-Token')
      return HttpResponse.json({ code: 'UNAUTHENTICATED', message: 'Войдите снова' }, { status: 401 })
    }))
    useAuthStore.setState({ userId: user.id, csrfToken: 'secure-token' })
    await expect(apiFetch('/api/me', { method: 'POST', schema: UserSchema })).rejects.toMatchObject({ status: 401 })
    expect(identity).toBeNull()
    expect(csrf).toBe('secure-token')
    expect(useAuthStore.getState().userId).toBeNull()
  })
})
