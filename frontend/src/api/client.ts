import { useAuthStore } from '../stores/auth'
import { ApiErrorBodySchema, type ZodTypeLike } from './schemas'

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

const BASE_URL = import.meta.env.VITE_API_URL || ''

function resolveUrl(path: string): string {
  const base = BASE_URL || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000')
  return `${base}${path}`
}

export async function apiFetch<T>(
  path: string,
  opts: { method?: 'GET' | 'POST'; body?: unknown; schema: ZodTypeLike<T> },
): Promise<T> {
  const userId = useAuthStore.getState().userId
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (userId) headers['x-user-id'] = userId

  let res: Response
  try {
    res = await fetch(resolveUrl(path), {
      method: opts.method ?? 'GET',
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    })
  } catch {
    throw new ApiError(0, 'Сеть недоступна. Проверь подключение и попробуй ещё раз', 'NETWORK')
  }

  const json: unknown = await res.json().catch(() => null)
  if (!res.ok) {
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
