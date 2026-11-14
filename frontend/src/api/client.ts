import { useAuthStore } from '../stores/auth'
import { ApiErrorBodySchema, type ZodTypeLike } from './schemas'
import { isMockMode } from './auth'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly code: string = 'UNKNOWN',
  ) {
    super(message)
    this.name = 'ApiError'
  }
  get isForbidden(): boolean {
    return this.status === 403
  }
}

export function getErrorMessage(err: unknown, fallback = 'Что-то пошло не так. Попробуй ещё раз'): string {
  if (err instanceof ApiError) return err.message
  if (err instanceof Error && err.message) return err.message
  return fallback
}

const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

function resolveUrl(path: string): string {
  const base = BASE_URL || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000')
  return `${base}${path}`
}

export async function apiFetch<T>(
  path: string,
  opts: { method?: 'GET' | 'POST' | 'DELETE'; body?: unknown; schema: ZodTypeLike<T> },
): Promise<T> {
  const { userId, csrfToken } = useAuthStore.getState()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (isMockMode && userId) headers['x-user-id'] = userId
  if (!isMockMode && csrfToken && opts.method !== undefined && opts.method !== 'GET') headers['X-CSRF-Token'] = csrfToken

  let res: Response
  try {
    res = await fetch(resolveUrl(path), {
      method: opts.method ?? 'GET',
      credentials: 'include',
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    })
  } catch {
    throw new ApiError(0, 'Сеть недоступна. Проверь подключение и попробуй ещё раз', 'NETWORK')
  }

  const json: unknown = await res.json().catch(() => null)
  if (!res.ok) {
    if (!isMockMode && res.status === 401) useAuthStore.setState({ userId: null, csrfToken: null })
    const parsed = ApiErrorBodySchema.safeParse(json)
    if (parsed.success) throw new ApiError(res.status, parsed.data.message, parsed.data.code)
    throw new ApiError(res.status, `Сервис вернул ошибку ${res.status}`, `HTTP_${res.status}`)
  }

  const parsed = opts.schema.safeParse(json)
  if (!parsed.success) {
    throw new ApiError(500, 'Сервис вернул данные в неожиданном формате', 'VALIDATION')
  }
  return parsed.data
}
