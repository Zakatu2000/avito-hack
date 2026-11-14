import { beforeEach, expect, it, vi } from 'vitest'
import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './setup'
import { renderWithProviders } from './helpers'
import { useAuthStore } from '../src/stores/auth'
import { AdaptationPlanPage } from '../src/pages/AdaptationPlanPage'
import { ChatPage } from '../src/pages/ChatPage'
import { KbPage } from '../src/pages/KbPage'
import { MetricsPage } from '../src/pages/MetricsPage'
import { PortalRequestForm } from '../src/pages/PortalRequestForm'
import { PortalRequestActions } from '../src/components/PortalRequestActions'
import type { Request } from '../src/api/schemas'

vi.mock('../src/api/auth', async (original) => ({
  ...await original<typeof import('../src/api/auth')>(), isMockMode: false,
}))
vi.mock('../src/stores/auth', async (original) => {
  const module = await original<typeof import('../src/stores/auth')>()
  return { ...module, useAuthStore: module.createAuthStore(false) }
})

const json = HttpResponse.json
const user = { id: 'user-a', role: 'intern', name: 'Анна Тест', initials: 'АТ', roleLabel: 'Стажёр', team: 'Test' }
const item = { id: 'wk2-env', title: 'Настройка окружения', description: 'Запусти проект', nextStep: 'Открой README',
  status: 'not_started', deadline: 'до конца недели', actionLink: '/kb', requiresApproval: false,
  sources: ['Демо'], canWork: true, origin: 'portal', stage: 2, stageLabel: '2-я неделя', blockers: [], requests: [] }
const plan = { track: 'backend', stage: 'week-2', firstTask: null,
  items: [item], quickStart: [{ id: 'environment', title: 'Окружение', items: [item], done: false }],
  nextStep: item, blockers: [{ itemId: item.id, title: item.title, reason: 'Нет доступа', action: '/requests/new/access' }] }
const hit = { chunkId: 'a', title: 'Источник', section: 'Учебная инструкция', snippet: 'README', url: null,
  sourceLocator: 'Чек-лист · строка 5', synthetic: true, sourceType: 'educational',
  sourceStatus: 'reconstructed', estimatedMinutes: 10, difficulty: 'introductory' }
const request: Request = { id: 'req-0123456789', kind: 'technical_support', status: 'draft',
  authorId: user.id, authorName: user.name, history: [], approvers: [], createdAt: '2026-01-01', updatedAt: '2026-01-01',
  payload: { kind: 'technical_support', title: 'Стенд' }, allowedActions: ['edit', 'send'] }
const button = (name: string) => screen.getByRole('button', { name })

beforeEach(() => {
  useAuthStore.setState({ userId: user.id, csrfToken: 'csrf', ready: true })
  server.use(
    http.get('*/api/me', () => json(user)),
    http.get('*/api/adaptation/plan', () => json(plan)),
    http.get('*/api/requests', () => json([])),
    http.get('*/api/kb/search', () => json([hit])),
    http.get('*/api/kb', () => json([])),
    http.get('*/api/contacts', () => json([])),
  )
})

function form(kind: string) {
  renderWithProviders(<Routes><Route path="/requests/new/:kind" element={<PortalRequestForm />} />
    <Route path="/requests/:requestId/edit" element={<PortalRequestForm />} />
    <Route path="/requests" element={<p>Запросы сохранены</p>} /></Routes>, { route: kind.startsWith('/') ? kind : '/requests/new/' + kind })
}

it('сохраняет черновик техподдержки с ключом повторной отправки', async () => {
  let submitted: unknown
  let key: string | null = null
  server.use(http.post('*/api/requests/technical_support', async ({ request: req }) => {
    key = req.headers.get('Idempotency-Key')
    submitted = await req.json()
    return json(request)
  }))
  form('technical_support')
  await userEvent.click(button('Отправить заявку'))
  expect(await screen.findByRole('alert')).toHaveTextContent('обязательные поля')
  fireEvent.change(screen.getByLabelText('Заголовок'), { target: { value: 'Стенд' } })
  fireEvent.change(screen.getByLabelText('Категория'), { target: { value: 'environment' } })
  await userEvent.click(button('Сохранить черновик'))
  expect(await screen.findByText('Запросы сохранены')).toBeInTheDocument()
  expect(key).toBeTruthy()
  expect(submitted).toEqual({ title: 'Стенд', category: 'environment', priority: 'normal', saveDraft: true })
})

it('редактирует и отправляет сохранённый черновик', async () => {
  const operations: string[] = []
  server.use(http.get('*/api/requests', () => json([request])),
    http.post('*/api/requests/:id/:operation', async ({ params }) => {
      operations.push(String(params.operation))
      return json(request)
    }))
  form('/requests/' + request.id + '/edit')
  await screen.findByLabelText('Заголовок')
  fireEvent.change(screen.getByLabelText('Категория'), { target: { value: 'git' } })
  fireEvent.change(screen.getByLabelText('Описание'), { target: { value: 'Ошибка командной строки' } })
  await userEvent.click(button('Отправить заявку'))
  expect(await screen.findByText('Запросы сохранены')).toBeInTheDocument()
  expect(operations).toEqual(['edit', 'send'])
})

it('ищет учебный материал перед отправкой заявки', async () => {
  server.use(http.post('*/api/requests/learning_request', () => json(request)))
  form('learning_request')
  fireEvent.change(screen.getByLabelText('Тема'), { target: { value: 'Архитектура' } })
  fireEvent.change(screen.getByLabelText('Причина запроса'), { target: { value: 'Первая задача' } })
  await userEvent.click(button('Отправить заявку'))
  expect(await screen.findByRole('alert')).toHaveTextContent('Сначала найдите')
  await userEvent.click(button('Найти материалы'))
  expect(await screen.findByText('Учебная инструкция')).toBeInTheDocument()
  await userEvent.click(button('Отправить заявку'))
  expect(await screen.findByText('Запросы сохранены')).toBeInTheDocument()
})

it('отправляет результат, передаёт ошибки согласования и повторяет попытку', async () => {
  let attempts = 0
  server.use(http.post('*/api/requests/:id/resolve', async ({ request: req }) => {
    expect(await req.json()).toEqual({ result: 'Стенд восстановлен' })
    return ++attempts === 1 ? json({ code: 'CONFLICT', message: 'Обновите заявку' }, { status: 409 }) : json(request)
  }))
  renderWithProviders(<PortalRequestActions request={{ ...request, status: 'in_progress', allowedActions: ['resolve'] }} />)
  await userEvent.click(button('Предложить решение'))
  fireEvent.change(screen.getByLabelText('Результат'), { target: { value: 'Стенд восстановлен' } })
  await userEvent.click(button('Сохранить'))
  expect(await screen.findByRole('alert')).toHaveTextContent('Обновите заявку')
  await userEvent.click(button('Сохранить'))
  expect(await screen.findByText('Запрос обновлён')).toBeInTheDocument()
})

it('показывает общий план, блокеры и отправляет переход пункта', async () => {
  let transition: unknown
  server.use(http.post('*/api/checklist/items/wk2-env/status', async ({ request: req }) => {
    transition = await req.json()
    return json([])
  }))
  renderWithProviders(<AdaptationPlanPage />)
  expect(await screen.findByRole('heading', { name: 'Быстрый старт' })).toBeInTheDocument()
  expect(screen.getByText('Нет доступа', { exact: false })).toBeInTheDocument()
  const row = within(document.querySelector('.quick-start') as HTMLElement)
  await userEvent.click(row.getByRole('button', { name: 'Начать' }))
  await vi.waitFor(() => expect(transition).toEqual({ status: 'in_progress' }))
})

it('показывает измеренные значения и пустые выборки', async () => {
  const empty = { value: null, sampleSize: 0 }
  server.use(http.get('*/api/adaptation/metrics', () => json({ origin: 'measured', firstTaskMinutes: empty,
    blockerMinutes: empty, requestMinutes: empty, withoutMentor: { value: 0.5, sampleSize: 2 },
    quickStart: { value: 0.6, sampleSize: 1 }, manualActionsAvoided: empty })))
  renderWithProviders(<MetricsPage />)
  expect(await screen.findByText('50 %')).toBeInTheDocument()
  expect(screen.getAllByText('Недостаточно данных')).toHaveLength(4)
})

it('показывает источники по фильтрам в базе знаний', async () => {
  renderWithProviders(<KbPage />, { route: '/kb?q=README' })
  expect(await screen.findByText('Учебная инструкция')).toBeInTheDocument()
  expect(screen.getByText('Чек-лист · строка 5')).toBeInTheDocument()
})

it('обрабатывает IME и многострочный ввод, показывает источник и отправляет отзыв', async () => {
  let submitted: Record<string, unknown> | undefined
  server.use(
    http.get('*/api/chat/config', () => json({ aiMode: 'live' })),
    http.post('*/api/chat', async ({ request: req }) => {
      submitted = await req.json() as Record<string, unknown>
      return json({ intentId: 'learn', text: 'Посмотри README', actions: [], sources: [hit],
        answerMethod: 'model', aiMode: 'live', messageId: submitted.messageId })
    }),
    http.post('*/api/chat/feedback', () => json({ ok: true })),
  )
  renderWithProviders(<ChatPage />, { route: '/chat?task=wk2-env' })
  expect(await screen.findByText('ИИ подключён · часть ответов по правилам')).toBeInTheDocument()
  const input = screen.getByRole('textbox', { name: 'Сообщение боту' })
  fireEvent.compositionStart(input)
  fireEvent.keyDown(input, { key: 'Enter', isComposing: true })
  expect(submitted).toBeUndefined()
  fireEvent.compositionEnd(input)
  fireEvent.change(input, { target: { value: 'Первая строка' } })
  await userEvent.type(input, '{Shift>}{Enter}{/Shift}Вторая строка{Enter}')
  expect(await screen.findByText('Ответ с ИИ')).toBeInTheDocument()
  expect(submitted).toMatchObject({ message: 'Первая строка\nВторая строка', taskId: 'wk2-env' })
  await userEvent.click(button('Решено'))
  expect(await screen.findByText('Отзыв сохранён')).toBeInTheDocument()
})
