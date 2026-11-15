import { HttpResponse, http, type PathParams } from 'msw'
import { z } from 'zod'
import {
  AccessPayloadSchema,
  ItemStatusSchema,
  LeavePayloadSchema,
  type Checklist,
  type ItemStatus,
  type Request as BuddyRequest,
  type Role,
  type User,
} from '../api/schemas'
import { createKeywordEngine, type BotFallback, type BotIntent } from '../chat/engine'
import { getDb, mutateDb } from './db'
import accessSystemsFixture from './fixtures/access-systems.json'
import chatFallbackFixture from './fixtures/chat-fallback.json'
import chatIntentsFixture from './fixtures/chat-intents.json'
import checklistFixture from './fixtures/checklist.json'
import contactsFixture from './fixtures/contacts.json'
import kbArticlesFixture from './fixtures/kb-articles.json'
import metricsFixture from './fixtures/metrics.json'
import usersFixture from './fixtures/users.json'
import { shouldSimulateFailure, simulateLatency } from './simulate'

const USERS = usersFixture as User[]
const APPROVERS: Role[] = ['mentor', 'lead']

function errorJson(status: number, message: string, code: string) {
  return HttpResponse.json({ message, code }, { status })
}

function currentUser(request: Request): User | null {
  const userId = request.headers.get('x-user-id')
  if (!userId) return null
  return USERS.find((u) => u.id === userId) ?? null
}

function authError(request: Request) {
  const user = currentUser(request)
  if (!user) return errorJson(401, 'Нужно войти тестовым пользователем', 'UNAUTHENTICATED')
  return null
}

async function withSimulation(handler: () => Promise<Response> | Response) {
  await simulateLatency()
  if (shouldSimulateFailure()) {
    return errorJson(500, 'Имитация сбоя сервиса (включена в dev-панели)', 'SIMULATED_FAILURE')
  }
  return handler()
}

function flatItems() {
  const stages = checklistFixture as unknown as Checklist
  return stages.flatMap((stage) => stage.items.map((item) => ({ ...item, stageId: stage.id })))
}

function buildChecklist(userId: string): Checklist {
  const db = getDb()
  const progress = db.progress[userId] ?? {}
  return (checklistFixture as unknown as Checklist).map((stage) => ({
    ...stage,
    items: stage.items.map((item) => ({
      ...item,
      status: progress[item.id] ?? ('not_started' as ItemStatus),
    })),
  }))
}

function nextRequestNumber(db: ReturnType<typeof getDb>): number {
  return db.requests.reduce((max, r) => {
    const n = Number.parseInt(r.id.replace(/\D+/g, ''), 10)
    return Number.isFinite(n) ? Math.max(max, n) : max
  }, 1000)
}

function makeRequest(
  partial: Omit<BuddyRequest, 'id' | 'createdAt' | 'updatedAt' | 'history'>,
  draft: boolean,
): BuddyRequest {
  const now = new Date().toISOString()
  const request: BuddyRequest = {
    ...partial,
    id: `req-${nextRequestNumber(getDb()) + 1}`,
    createdAt: now,
    updatedAt: now,
    history: [{ at: now, status: draft ? 'Создан черновик' : 'Отправлен', by: partial.authorName }],
  }
  mutateDb((db) => {
    db.requests.push(request)
  })
  return request
}

const Body = {
  status: z.object({ status: ItemStatusSchema }),
  reject: z.object({ comment: z.string().max(300).optional() }),
  chat: z.object({ message: z.string().min(1).max(500), conversationId: z.string().optional() }),
}

/* Мок постоянных чатов: в памяти, по аналогии с серверными portal_conversations. */
interface MockChatMessage {
  id: number
  role: 'user' | 'bot'
  text: string
  actions?: { id: string; label: string; kind: 'navigate' | 'contact'; target: string | null }[]
}
interface MockChat {
  id: string
  userId: string
  title: string
  createdAt: string
  updatedAt: string
  messages: MockChatMessage[]
}
const MOCK_CHAT_KEY = 'ai-buddy-mock-chats-v1'

function isMockChat(value: unknown): value is MockChat {
  if (!value || typeof value !== 'object') return false
  const chat = value as Partial<MockChat>
  return typeof chat.id === 'string'
    && typeof chat.userId === 'string'
    && typeof chat.title === 'string'
    && typeof chat.createdAt === 'string'
    && typeof chat.updatedAt === 'string'
    && Array.isArray(chat.messages)
    && chat.messages.every((message) => message
      && typeof message.id === 'number'
      && (message.role === 'user' || message.role === 'bot')
      && typeof message.text === 'string'
      && (message.actions === undefined || Array.isArray(message.actions)))
}

function loadMockChats(): MockChat[] {
  if (typeof localStorage === 'undefined') return []
  try {
    const value: unknown = JSON.parse(localStorage.getItem(MOCK_CHAT_KEY) ?? '[]')
    return Array.isArray(value) ? value.filter(isMockChat) : []
  } catch {
    return []
  }
}

const mockChats: MockChat[] = loadMockChats()
let mockChatSeq = mockChats.reduce((max, chat) => {
  const sequence = Number.parseInt(chat.id.slice('chat-'.length), 16)
  return Number.isFinite(sequence) ? Math.max(max, sequence) : max
}, 0)

function persistMockChats(): void {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(MOCK_CHAT_KEY, JSON.stringify(mockChats))
  } catch {
    /* browser storage is optional in the mock environment */
  }
}

export function resetMockChats(): void {
  mockChats.splice(0, mockChats.length)
  mockChatSeq = 0
  if (typeof localStorage !== 'undefined') localStorage.removeItem(MOCK_CHAT_KEY)
}

function ownedChat(request: Request, id: string): MockChat | null {
  const user = currentUser(request)
  const chat = mockChats.find((c) => c.id === id)
  return user && chat && chat.userId === user.id ? chat : null
}

function chatTitle(text: string): string {
  return text.replace(/\s+/g, ' ').trim().slice(0, 60) || 'Новый чат'
}

export const handlers = [
  /* ---------- Пользователи (без задержек и сбоев: вход должен работать всегда) ---------- */
  http.get('/api/users', () => HttpResponse.json(usersFixture)),

  http.get('/api/me', ({ request }) => {
    const user = currentUser(request)
    if (!user) return errorJson(401, 'Нужно войти тестовым пользователем', 'UNAUTHENTICATED')
    return HttpResponse.json(user)
  }),

  /* ---------- Чек-лист адаптации ---------- */
  http.get('/api/checklist', async ({ request }) => {
    const denied = authError(request)
    if (denied) return denied
    return withSimulation(() => {
      const user = currentUser(request)!
      return HttpResponse.json(buildChecklist(user.id))
    })
  }),

  http.post<PathParams, { status: string }>('/api/checklist/items/:id/status', async ({ request, params }) => {
    const denied = authError(request)
    if (denied) return denied
    const parsed = Body.status.safeParse(await request.json().catch(() => null))
    if (!parsed.success) return errorJson(400, 'Некорректный статус пункта', 'BAD_REQUEST')
    return withSimulation(() => {
      const user = currentUser(request)!
      const itemId = String(params.id)
      const item = flatItems().find((i) => i.id === itemId)
      if (!item) return errorJson(404, 'Пункт чек-листа не найден', 'NOT_FOUND')
      const target = parsed.data.status
      const current = getDb().progress[user.id]?.[itemId] ?? 'not_started'
      const isApprover = APPROVERS.includes(user.role)

      if (isApprover) {
        if (target !== 'done') {
          return errorJson(400, 'Наставник может только подтверждать пункты', 'BAD_REQUEST')
        }
      } else {
        const allowed: Record<string, ItemStatus[]> = {
          not_started: ['in_progress'],
          in_progress: item.requiresApproval ? ['pending_approval'] : ['done'],
          pending_approval: [],
          done: [],
        }
        if (!allowed[current]?.includes(target)) {
          return errorJson(
            403,
            'Стажёр не может сам подтвердить этот пункт — дождись наставника',
            'FORBIDDEN',
          )
        }
      }

      mutateDb((db) => {
        db.progress[user.id] = db.progress[user.id] ?? {}
        db.progress[user.id][itemId] = target
      })
      return HttpResponse.json(buildChecklist(user.id))
    })
  }),

  /* ---------- Запросы ---------- */
  http.get('/api/requests', ({ request }) => {
    const denied = authError(request)
    if (denied) return denied
    return withSimulation(() => {
      const user = currentUser(request)!
      const url = new URL(request.url)
      const scope = url.searchParams.get('scope')
      if (scope === 'queue') {
        if (!APPROVERS.includes(user.role)) {
          return errorJson(403, 'Очередь согласования доступна наставнику и руководителю', 'FORBIDDEN')
        }
        return HttpResponse.json(
          getDb().requests.filter((r) => r.status === 'sent' || r.status === 'approving'),
        )
      }
      const list = APPROVERS.includes(user.role)
        ? getDb().requests
        : getDb().requests.filter((r) => r.authorId === user.id)
      return HttpResponse.json(list)
    })
  }),

  http.post('/api/requests/leave', async ({ request }) => {
    const denied = authError(request)
    if (denied) return denied
    const body = await request.json().catch(() => null)
    const payload = LeavePayloadSchema.omit({ kind: true }).safeParse(body)
    if (!payload.success) {
      return errorJson(400, 'Проверь поля формы отгула: даты и причина', 'BAD_REQUEST')
    }
    return withSimulation(() => {
      const user = currentUser(request)!
      const saveDraft = Boolean((body as { saveDraft?: boolean } | null)?.saveDraft)
      const request_ = makeRequest(
        {
          kind: 'leave',
          authorId: user.id,
          authorName: user.name,
          status: saveDraft ? 'draft' : 'sent',
          approvers: ['Марина Ким', 'Олег Ветров'],
          payload: { kind: 'leave', ...payload.data },
        },
        saveDraft,
      )
      return HttpResponse.json(request_, { status: 201 })
    })
  }),

  http.post('/api/requests/access', async ({ request }) => {
    const denied = authError(request)
    if (denied) return denied
    const body = await request.json().catch(() => null)
    const payload = AccessPayloadSchema.omit({ kind: true }).safeParse(body)
    if (!payload.success) {
      return errorJson(400, 'Проверь поля формы доступа: система и обоснование', 'BAD_REQUEST')
    }
    return withSimulation(() => {
      const user = currentUser(request)!
      const saveDraft = Boolean((body as { saveDraft?: boolean } | null)?.saveDraft)
      const request_ = makeRequest(
        {
          kind: 'access',
          authorId: user.id,
          authorName: user.name,
          status: saveDraft ? 'draft' : 'sent',
          approvers: ['Олег Ветров'],
          payload: { kind: 'access', ...payload.data },
        },
        saveDraft,
      )
      return HttpResponse.json(request_, { status: 201 })
    })
  }),

  http.post<PathParams, { comment?: string }>('/api/requests/:id/approve', async ({ request, params }) => {
    const denied = authError(request)
    if (denied) return denied
    return withSimulation(() => {
      const user = currentUser(request)!
      if (!APPROVERS.includes(user.role)) {
        return errorJson(403, 'Согласовывать запросы могут только наставник и руководитель', 'FORBIDDEN')
      }
      const id = String(params.id)
      const req = getDb().requests.find((r) => r.id === id)
      if (!req) return errorJson(404, 'Запрос не найден', 'NOT_FOUND')
      if (req.status === 'draft') return errorJson(400, 'Запрос ещё в черновике', 'BAD_REQUEST')
      if (req.status === 'approved' || req.status === 'rejected') {
        return errorJson(400, 'Запрос уже закрыт', 'BAD_REQUEST')
      }
      const nextStatus = req.status === 'sent' ? 'approving' : 'approved'
      mutateDb((db) => {
        const target = db.requests.find((r) => r.id === id)!
        target.status = nextStatus
        target.updatedAt = new Date().toISOString()
        target.history.push({
          at: target.updatedAt,
          status: nextStatus === 'approving' ? 'На согласовании' : req.kind === 'access' ? 'Выдан' : 'Одобрен',
          by: user.name,
        })
      })
      return HttpResponse.json(getDb().requests.find((r) => r.id === id))
    })
  }),

  http.post<PathParams, { comment?: string }>('/api/requests/:id/reject', async ({ request, params }) => {
    const denied = authError(request)
    if (denied) return denied
    const parsed = Body.reject.safeParse(await request.json().catch(() => ({})))
    return withSimulation(() => {
      const user = currentUser(request)!
      if (!APPROVERS.includes(user.role)) {
        return errorJson(403, 'Отклонять запросы могут только наставник и руководитель', 'FORBIDDEN')
      }
      const id = String(params.id)
      const req = getDb().requests.find((r) => r.id === id)
      if (!req) return errorJson(404, 'Запрос не найден', 'NOT_FOUND')
      if (req.status === 'approved' || req.status === 'rejected') {
        return errorJson(400, 'Запрос уже закрыт', 'BAD_REQUEST')
      }
      mutateDb((db) => {
        const target = db.requests.find((r) => r.id === id)!
        target.status = 'rejected'
        target.updatedAt = new Date().toISOString()
        target.history.push({
          at: target.updatedAt,
          status: 'Отклонён',
          by: user.name,
          comment: parsed.success ? parsed.data.comment : undefined,
        })
      })
      return HttpResponse.json(getDb().requests.find((r) => r.id === id))
    })
  }),

  http.post('/api/requests/:id/send', ({ request, params }) => {
    const denied = authError(request)
    if (denied) return denied
    return withSimulation(() => {
      const user = currentUser(request)!
      const id = String((params as PathParams).id)
      const req = getDb().requests.find((r) => r.id === id)
      if (!req) return errorJson(404, 'Запрос не найден', 'NOT_FOUND')
      if (req.authorId !== user.id) {
        return errorJson(403, 'Отправить чужой запрос нельзя', 'FORBIDDEN')
      }
      if (req.status !== 'draft') return errorJson(400, 'Отправить можно только черновик', 'BAD_REQUEST')
      mutateDb((db) => {
        const target = db.requests.find((r) => r.id === id)!
        target.status = 'sent'
        target.updatedAt = new Date().toISOString()
        target.history.push({ at: target.updatedAt, status: 'Отправлен', by: user.name })
      })
      return HttpResponse.json(getDb().requests.find((r) => r.id === id))
    })
  }),

  /* ---------- Справочники ---------- */
  http.get('/api/contacts', ({ request }) => {
    const denied = authError(request)
    if (denied) return denied
    return withSimulation(() => HttpResponse.json(contactsFixture))
  }),

  http.get('/api/kb', ({ request }) => {
    const denied = authError(request)
    if (denied) return denied
    return withSimulation(() => HttpResponse.json(kbArticlesFixture))
  }),

  http.get('/api/access-systems', ({ request }) => {
    const denied = authError(request)
    if (denied) return denied
    return withSimulation(() => HttpResponse.json(accessSystemsFixture))
  }),

  http.get('/api/metrics', ({ request }) => {
    const denied = authError(request)
    if (denied) return denied
    return withSimulation(() => HttpResponse.json(metricsFixture))
  }),

  http.get('/api/interns', ({ request }) => {
    const denied = authError(request)
    if (denied) return denied
    return withSimulation(() => {
      const user = currentUser(request)!
      if (!APPROVERS.includes(user.role)) {
        return errorJson(403, 'Раздел доступен наставнику и руководителю', 'FORBIDDEN')
      }
      const interns = USERS.filter((u) => u.role === 'intern')
      return HttpResponse.json(
        interns.map((intern) => {
          const checklist = buildChecklist(intern.id)
          const items = checklist.flatMap((s) => s.items)
          const done = items.filter((i) => i.status === 'done').length
          const next = items.find((i) => i.status !== 'done')
          return {
            user: intern,
            progress: { done, total: items.length, percent: Math.round((done / items.length) * 100) },
            nextStepTitle: next?.title ?? null,
          }
        }),
      )
    })
  }),

  /* ---------- Очередь подтверждения пунктов чек-листа ---------- */
  http.get('/api/pending-items', ({ request }) => {
    const denied = authError(request)
    if (denied) return denied
    return withSimulation(() => {
      const user = currentUser(request)!
      if (!APPROVERS.includes(user.role)) {
        return errorJson(403, 'Очередь подтверждения доступна наставнику и руководителю', 'FORBIDDEN')
      }
      const pending = USERS.filter((u) => u.role === 'intern').flatMap((intern) => {
        const checklist = buildChecklist(intern.id)
        return checklist
          .flatMap((stage) => stage.items)
          .filter((item) => item.status === 'pending_approval')
          .map((item) => ({
            userId: intern.id,
            userName: intern.name,
            itemId: item.id,
            title: item.title,
            nextStep: item.nextStep,
          }))
      })
      return HttpResponse.json(pending)
    })
  }),

  http.post<PathParams, { userId: string }>('/api/checklist/items/:id/approve', async ({ request, params }) => {
    const denied = authError(request)
    if (denied) return denied
    const body = (await request.json().catch(() => null)) as { userId?: string } | null
    return withSimulation(() => {
      const user = currentUser(request)!
      if (!APPROVERS.includes(user.role)) {
        return errorJson(403, 'Подтверждать пункты могут только наставник и руководитель', 'FORBIDDEN')
      }
      const itemId = String(params.id)
      const targetUserId = body?.userId
      const target = USERS.find((u) => u.id === targetUserId && u.role === 'intern')
      if (!target) return errorJson(404, 'Стажёр не найден', 'NOT_FOUND')
      const item = flatItems().find((i) => i.id === itemId)
      if (!item) return errorJson(404, 'Пункт чек-листа не найден', 'NOT_FOUND')
      mutateDb((db) => {
        db.progress[target.id] = db.progress[target.id] ?? {}
        db.progress[target.id][itemId] = 'done'
      })
      const pending = USERS.filter((u) => u.role === 'intern').flatMap((intern) =>
        buildChecklist(intern.id)
          .flatMap((stage) => stage.items)
          .filter((it) => it.status === 'pending_approval')
          .map((it) => ({
            userId: intern.id,
            userName: intern.name,
            itemId: it.id,
            title: it.title,
            nextStep: it.nextStep,
          })),
      )
      return HttpResponse.json(pending)
    })
  }),

  /* ---------- Чаты: список, создание, удаление, история ---------- */
  http.get('/api/chats', ({ request }) => {
    const denied = authError(request)
    if (denied) return denied
    const user = currentUser(request)!
    return HttpResponse.json(
      mockChats
        .filter((c) => c.userId === user.id)
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
        .map(({ id, title, createdAt, updatedAt }) => ({ id, title, createdAt, updatedAt })),
    )
  }),

  http.post('/api/chats', async ({ request }) => {
    const denied = authError(request)
    if (denied) return denied
    const body = await request.json().catch(() => ({}))
    const parsed = z.object({ title: z.string().trim().min(1).max(120).optional() })
      .strict()
      .safeParse(body)
    if (!parsed.success) return errorJson(400, 'Некорректное название чата', 'BAD_REQUEST')
    const user = currentUser(request)!
    const now = new Date().toISOString()
    const chat: MockChat = {
      id: `chat-${(++mockChatSeq).toString(16).padStart(24, '0')}`,
      userId: user.id,
      title: parsed.data.title || 'Новый чат',
      createdAt: now,
      updatedAt: now,
      messages: [],
    }
    mockChats.push(chat)
    persistMockChats()
    return HttpResponse.json(
      { id: chat.id, title: chat.title, createdAt: chat.createdAt, updatedAt: chat.updatedAt },
      { status: 201 },
    )
  }),

  http.delete('/api/chats/:id', ({ request, params }) => {
    const denied = authError(request)
    if (denied) return denied
    const chat = ownedChat(request, String(params.id))
    if (!chat) return errorJson(404, 'Чат не найден', 'NOT_FOUND')
    mockChats.splice(mockChats.indexOf(chat), 1)
    persistMockChats()
    return new HttpResponse(null, { status: 204 })
  }),

  http.get('/api/chats/:id/messages', ({ request, params }) => {
    const denied = authError(request)
    if (denied) return denied
    const chat = ownedChat(request, String(params.id))
    if (!chat) return errorJson(404, 'Чат не найден', 'NOT_FOUND')
    return HttpResponse.json(chat.messages)
  }),

  /* ---------- Чат с детерминированным ботом ---------- */
  http.post('/api/chat', async ({ request }) => {
    const denied = authError(request)
    if (denied) return denied
    const parsed = Body.chat.safeParse(await request.json().catch(() => null))
    if (!parsed.success) return errorJson(400, 'Пустое сообщение', 'BAD_REQUEST')
    return withSimulation(() => {
      const user = currentUser(request)!
      let chat: MockChat | null = null
      if (parsed.data.conversationId) {
        chat = ownedChat(request, parsed.data.conversationId)
        if (!chat) return errorJson(404, 'Чат не найден', 'NOT_FOUND')
      } else {
        const now = new Date().toISOString()
        chat = {
          id: `chat-${(++mockChatSeq).toString(16).padStart(24, '0')}`,
          userId: user.id,
          title: chatTitle(parsed.data.message),
          createdAt: now,
          updatedAt: now,
          messages: [],
        }
        mockChats.push(chat)
      }
      const checklist = buildChecklist(user.id)
      const next = checklist.flatMap((s) => s.items).find((i) => i.status !== 'done')
      const mentor = contactsFixture.find((c) => c.id === 'c-mentor')
      const engine = createKeywordEngine(
        chatIntentsFixture as unknown as BotIntent[],
        chatFallbackFixture as unknown as BotFallback,
      )
      const reply = engine.reply(parsed.data.message, {
        userName: user.name.split(' ')[0] ?? user.name,
        mentorName: mentor?.name ?? 'наставница',
        nextStepTitle: next?.title ?? null,
      })
      const base = chat.messages.length
      chat.messages.push({ id: base + 1, role: 'user', text: parsed.data.message })
      chat.messages.push({ id: base + 2, role: 'bot', text: reply.text, actions: reply.actions })
      chat.updatedAt = new Date().toISOString()
      persistMockChats()
      return HttpResponse.json({ ...reply, conversationId: chat.id })
    })
  }),
]
