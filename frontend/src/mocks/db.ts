import type { ItemStatus, Request } from '../api/schemas'

const DB_KEY = 'ai-buddy-db-v1'

interface DbShape {
  requests: Request[]
  progress: Record<string, Record<string, ItemStatus>>
}

function isoShiftDays(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString()
}

function seed(): DbShape {
  return {
    requests: [
      {
        id: 'req-leave-1001',
        kind: 'leave',
        authorId: 'u-intern-1',
        authorName: 'Аня Петрова',
        status: 'sent',
        createdAt: isoShiftDays(-2),
        updatedAt: isoShiftDays(-2),
        approvers: ['Марина Ким', 'Олег Ветров'],
        payload: {
          kind: 'leave',
          startDate: isoShiftDays(10).slice(0, 10),
          endDate: isoShiftDays(11).slice(0, 10),
          reason: 'personal',
          comment: 'Семейные обстоятельства',
        },
        history: [{ at: isoShiftDays(-2), status: 'Отправлен', by: 'Аня Петрова' }],
      },
      {
        id: 'req-access-1002',
        kind: 'access',
        authorId: 'u-intern-2',
        authorName: 'Марк Соколов',
        status: 'approving',
        createdAt: isoShiftDays(-1),
        updatedAt: isoShiftDays(-1),
        approvers: ['Олег Ветров'],
        payload: {
          kind: 'access',
          system: 'jira',
          justification: 'Нужен доступ к спринту стажёров для аналитических задач',
          durationDays: 90,
        },
        history: [
          { at: isoShiftDays(-1), status: 'Отправлен', by: 'Марк Соколов' },
          { at: isoShiftDays(-1), status: 'На согласовании', by: 'Олег Ветров' },
        ],
      },
    ],
    progress: {
      'u-intern-1': {
        'wk1-chats': 'done',
        'wk1-team': 'done',
        'wk1-access': 'in_progress',
        'wk1-1to1': 'pending_approval',
      },
      'u-intern-2': { 'wk1-chats': 'done' },
    },
  }
}

function load(): DbShape {
  if (typeof localStorage === 'undefined') return seed()
  try {
    const raw = localStorage.getItem(DB_KEY)
    if (!raw) return seed()
    const parsed = JSON.parse(raw) as DbShape
    if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.requests)) return seed()
    return parsed
  } catch {
    return seed()
  }
}

let cache: DbShape | null = null

export function getDb(): DbShape {
  if (!cache) cache = load()
  return cache
}

export function saveDb(): void {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(DB_KEY, JSON.stringify(cache))
  } catch {
    /* хранилище недоступно — работаем в памяти */
  }
}

export function mutateDb(fn: (db: DbShape) => void): void {
  fn(getDb())
  saveDb()
}

export function resetDb(): void {
  cache = seed()
  saveDb()
}
