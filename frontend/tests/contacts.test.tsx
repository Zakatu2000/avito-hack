import { beforeEach, expect, it, vi } from 'vitest'
import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from './setup'
import { renderWithProviders } from './helpers'
import { ContactsPage } from '../src/pages/ContactsPage'
import { useAuthStore } from '../src/stores/auth'
import type { Contact } from '../src/api/schemas'

vi.mock('../src/api/auth', async (original) => ({
  ...await original<typeof import('../src/api/auth')>(), isMockMode: false,
}))
vi.mock('../src/stores/auth', async (original) => {
  const real = await original<typeof import('../src/stores/auth')>()
  return { ...real, useAuthStore: real.createAuthStore(false) }
})

const account = { id: 'contacts-user', name: 'Анна Стажёр', role: 'intern', roleLabel: 'Стажёр', team: 'Тест', initials: 'АС' }
const mentor: Contact = { id: 'mentor-a', name: 'Алёна Соколова', role: 'Наставник', roleKey: 'mentor', source: 'team',
  helpsWith: ['Первые задачи'], channel: '', responseTime: '', tone: 'green' }
const lead: Contact = { ...mentor, id: 'lead-a', name: 'Алексей Ветров', role: 'Руководитель', roleKey: 'lead', tone: 'blue' }
const curator: Contact = { ...mentor, id: 'c-curator', name: 'Дима Лозовой', role: 'Куратор', roleKey: 'curator', source: 'demo' }

beforeEach(() => {
  useAuthStore.setState({ userId: account.id, csrfToken: 'test-csrf', ready: true })
  server.use(
    http.get('*/api/me', () => HttpResponse.json(account)),
    http.get('*/api/contacts', () => HttpResponse.json([mentor, lead, curator])),
  )
})

async function view() {
  renderWithProviders(<ContactsPage />)
  const search = await screen.findByRole('searchbox', { name: 'Что случилось?' })
  const result = within(screen.getByRole('region', { name: 'Рекомендация' }))
  return { search, result }
}

it('ведёт из VPN, репозитория, задачи, отгула и обучения в нужный раздел', async () => {
  const { search, result } = await view()
  const cases = [
    ['Не работает VPN', 'Создать обращение', '/requests/new/technical_support?category=network'],
    ['Нужен доступ к репозиторию', 'Открыть форму доступа', '/requests/new/access?system=repo'],
    ['Помогите с первой задачей', 'Запросить консультацию', '/requests/new/mentor_consultation?topic='],
    ['Как оформить отгул?', 'Открыть форму отгула', '/requests/new/leave'],
    ['Хочу изучить микросервисы', 'Открыть базу знаний', '/kb'],
  ]
  for (const [query, label, url] of cases) {
    fireEvent.change(search, { target: { value: query } })
    expect(result.getByRole('link', { name: label }).getAttribute('href')?.startsWith(url)).toBe(true)
  }
  expect(result.getByRole('link', { name: 'Запросить материал' })).toBeInTheDocument()
})

it('предлагает выбрать при совпадении тем, ищет по имени и сбрасывает фильтр', async () => {
  const { search, result } = await view()
  const directory = within(screen.getByRole('region', { name: 'Справочник контактов' }))
  fireEvent.change(search, { target: { value: 'Нужен доступ и не работает VPN' } })
  expect(result.getByText(/подходит несколько тем/i, { selector: '.body-secondary' })).toBeInTheDocument()
  await userEvent.click(result.getByRole('button', { name: 'Техническая проблема' }))
  expect(result.getByRole('link', { name: 'Создать обращение' })).toHaveAttribute('href', '/requests/new/technical_support?category=network')
  fireEvent.change(search, { target: { value: 'алена соколова' } })
  expect(directory.getByRole('heading', { name: mentor.name })).toBeInTheDocument()
  expect(directory.queryByRole('heading', { name: lead.name })).toBeNull()
  fireEvent.change(search, { target: { value: 'неизвестная ситуация' } })
  expect(result.getByRole('link', { name: 'Спросить AI-buddy' })).toHaveAttribute('href', '/chat')
  await userEvent.click(screen.getByRole('button', { name: 'Сбросить поиск' }))
  expect(search).toHaveFocus()
  expect(directory.getByText('Демо-контакт')).toBeInTheDocument()
})

it('предлагает руководителя при отсутствии наставника', async () => {
  server.use(http.get('*/api/contacts', () => HttpResponse.json([lead, curator])))
  const { result } = await view()
  await userEvent.click(screen.getByRole('button', { name: 'Первая задача' }))
  expect(result.getByText(/в команде пока нет наставника/i)).toBeInTheDocument()
  expect(result.getByText(lead.name, { exact: false })).toBeInTheDocument()
  expect(result.queryByRole('link', { name: 'Запросить консультацию' })).toBeNull()
  expect(result.getByRole('link', { name: 'Спросить AI-buddy' })).toBeInTheDocument()
})

it('редактирует и копирует сообщение, восстанавливает фокус и поддерживает ручное копирование', async () => {
  const user = userEvent.setup()
  const write = vi.spyOn(navigator.clipboard, 'writeText')
  await view()
  const prepare = screen.getByRole('button', { name: 'Подготовить сообщение — ' + mentor.name })
  await user.click(prepare)
  const draft = within(screen.getByRole('region', { name: 'Черновик сообщения' }))
  const field = draft.getByRole('textbox', { name: 'Текст сообщения' })
  expect(field).toHaveFocus()
  expect((field as HTMLTextAreaElement).value).toContain('Что уже попробовал')
  fireEvent.change(field, { target: { value: 'Нужна помощь с настройкой.' } })
  await user.click(draft.getByRole('button', { name: 'Скопировать текст' }))
  expect(write).toHaveBeenCalledWith('Нужна помощь с настройкой.')
  expect(draft.getByRole('status')).toHaveTextContent('Скопировано')
  write.mockRejectedValueOnce(new Error('clipboard blocked'))
  await user.click(draft.getByRole('button', { name: 'Скопировать текст' }))
  expect(draft.getByRole('status')).toHaveTextContent('Текст выделен')
  await user.click(draft.getByRole('button', { name: 'Закрыть черновик' }))
  expect(prepare).toHaveFocus()
  write.mockRestore()
})
