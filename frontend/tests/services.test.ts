import { beforeEach, describe, expect, it } from 'vitest'
import { ApiError } from '../src/api/client'
import { service } from '../src/services'
import { getDb, resetDb } from '../src/mocks/db'
import { useAuthStore } from '../src/stores/auth'
import { useDevStore } from '../src/stores/dev'

const login = useAuthStore.setState
const tomorrow = () => {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}

beforeEach(() => {
  resetDb()
  login({ userId: 'u-intern-1' })
})

describe('сервис: чек-лист (spec: frontend/specs/001-adaptation-track.md)', () => {
  it('возвращает этапы с прокинутыми статусами прогресса', async () => {
    const checklist = await service.getChecklist()
    expect(checklist).toHaveLength(5)
    expect(checklist[0]?.title).toBe('1-я неделя')
    const chats = checklist[0]?.items.find((i) => i.id === 'wk1-chats')
    expect(chats?.status).toBe('done')
    const solo = checklist[3]?.items.find((i) => i.id === 'm2-solo')
    expect(solo?.status).toBe('not_started')
  })

  it('стажёр переводит пункт с согласованием в «ждёт согласования»', async () => {
    await service.updateItemStatus('wk2-first-task', 'in_progress')
    await service.updateItemStatus('wk2-first-task', 'pending_approval')
    const checklist = await service.getChecklist()
    expect(checklist[1]?.items.find((i) => i.id === 'wk2-first-task')?.status).toBe('pending_approval')
  })

  it('стажёр не может сам подтвердить пункт с согласованием — 403 (spec: frontend/specs/004-roles-permissions.md)', async () => {
    await expect(service.updateItemStatus('m1-okr', 'done')).rejects.toMatchObject({
      status: 403,
      code: 'FORBIDDEN',
    })
  })

  it('наставник подтверждает пункт стажёра через очередь подтверждения', async () => {
    login({ userId: 'u-mentor-1' })
    const pending = await service.getPendingItems()
    expect(pending.some((p) => p.itemId === 'wk1-1to1' && p.userId === 'u-intern-1')).toBe(true)
    const after = await service.approveChecklistItem('wk1-1to1', 'u-intern-1')
    expect(after.some((p) => p.itemId === 'wk1-1to1')).toBe(false)
    login({ userId: 'u-intern-1' })
    const checklist = await service.getChecklist()
    expect(checklist[0]?.items.find((i) => i.id === 'wk1-1to1')?.status).toBe('done')
  })

  it('стажёру очередь подтверждения недоступна — 403', async () => {
    await expect(service.getPendingItems()).rejects.toMatchObject({ status: 403 })
  })
})

describe('сервис: запросы (specs: 002-access-request.md, 003-leave-request.md)', () => {
  it('создаёт отгул со статусом «отправлен» и историей', async () => {
    const request = await service.createLeaveRequest({
      startDate: tomorrow(),
      endDate: tomorrow(),
      reason: 'personal',
    })
    expect(request.status).toBe('sent')
    expect(request.history.at(-1)?.status).toBe('Отправлен')
    expect(request.approvers).toContain('Марина Ким')
  })

  it('сохраняет черновик отгула', async () => {
    const request = await service.createLeaveRequest({
      startDate: tomorrow(),
      endDate: tomorrow(),
      reason: 'other',
      saveDraft: true,
    })
    expect(request.status).toBe('draft')
  })

  it('отклоняет некорректные даты на клиенте zod-схемой', async () => {
    await expect(
      service.createLeaveRequest({ startDate: 'нет', endDate: tomorrow(), reason: 'other' }),
    ).rejects.toThrowError()
  })

  it('создаёт запрос доступа и прогоняет цепочку до «выдан»', async () => {
    const created = await service.requestAccess({
      system: 'confluence',
      justification: 'Нужен для чтения документации команды',
      durationDays: 90,
    })
    expect(created.status).toBe('sent')

    login({ userId: 'u-mentor-1' })
    const approving = await service.approveRequest(created.id)
    expect(approving.status).toBe('approving')
    const granted = await service.approveRequest(created.id)
    expect(granted.status).toBe('approved')
    expect(granted.history.at(-1)?.status).toBe('Выдан')
  })

  it('стажёр не может согласовать запрос — 403 (spec: frontend/specs/004-roles-permissions.md)', async () => {
    const seeded = getDb().requests.find((r) => r.id === 'req-leave-1001')
    expect(seeded).toBeDefined()
    await expect(service.approveRequest('req-leave-1001')).rejects.toMatchObject({ status: 403 })
  })

  it('руководитель отклоняет запрос с комментарием', async () => {
    login({ userId: 'u-lead-1' })
    const rejected = await service.rejectRequest('req-leave-1001', 'Нужны точные даты')
    expect(rejected.status).toBe('rejected')
    expect(rejected.history.at(-1)?.comment).toBe('Нужны точные даты')
  })

  it('стажёр видит только свои запросы, наставник — все', async () => {
    const mine = await service.listRequests()
    expect(mine.every((r) => r.authorId === 'u-intern-1')).toBe(true)
    login({ userId: 'u-mentor-1' })
    const all = await service.listRequests()
    expect(all.length).toBeGreaterThan(mine.length)
  })

  it('запросы переживают «перезагрузку страницы» — localStorage (spec: frontend/specs/006-mock-services.md)', async () => {
    const created = await service.createLeaveRequest({
      startDate: tomorrow(),
      endDate: tomorrow(),
      reason: 'vacation',
    })
    const raw = localStorage.getItem('ai-buddy-db-v1')
    expect(raw).toBeTruthy()
    const parsed = JSON.parse(raw!) as { requests: { id: string }[] }
    expect(parsed.requests.some((r) => r.id === created.id)).toBe(true)
  })
})

describe('сервис: роли и права (spec: frontend/specs/004-roles-permissions.md)', () => {
  it('очередь согласования недоступна стажёру — 403', async () => {
    await expect(service.listRequests('queue')).rejects.toMatchObject({ status: 403 })
  })

  it('наставник видит очередь из активных запросов', async () => {
    login({ userId: 'u-mentor-1' })
    const queue = await service.listRequests('queue')
    expect(queue.length).toBeGreaterThan(0)
    expect(queue.every((r) => r.status === 'sent' || r.status === 'approving')).toBe(true)
  })

  it('список стажёров с прогрессом доступен наставнику', async () => {
    login({ userId: 'u-mentor-1' })
    const interns = await service.getInterns()
    expect(interns).toHaveLength(2)
    expect(interns[0]?.progress.total).toBeGreaterThan(0)
    expect(interns[0]?.progress.percent).toBeGreaterThanOrEqual(0)
  })

  it('список стажёров недоступен стажёру — 403 с состоянием «нет доступа»', async () => {
    await expect(service.getInterns()).rejects.toBeInstanceOf(ApiError)
  })
})

describe('сервис: имитация сбоев и задержек (spec: frontend/specs/006-mock-services.md)', () => {
  it('возвращает 500 при включённом режиме сбоя', async () => {
    useDevStore.setState({ failureMode: 'always' })
    await expect(service.getChecklist()).rejects.toMatchObject({
      status: 500,
      code: 'SIMULATED_FAILURE',
    })
  })
})

describe('сервис: чат (spec: frontend/specs/005-chat-bot.md)', () => {
  it('отвечает по интенту и подставляет следующий шаг', async () => {
    const reply = await service.sendChatMessage('как оформить отгул?')
    expect(reply.intentId).toBe('leave')
    expect(reply.actions.length).toBeGreaterThan(0)
  })

  it('честно признаётся, когда вопрос не распознан', async () => {
    const reply = await service.sendChatMessage('квантовая запутанность')
    expect(reply.intentId).toBe('fallback')
    expect(reply.text).toContain('не понял')
    expect(reply.actions.some((a) => a.kind === 'contact')).toBe(true)
  })

  it('требует входа для общения с ботом', async () => {
    login({ userId: null })
    await expect(service.sendChatMessage('привет')).rejects.toMatchObject({ status: 401 })
  })
})
