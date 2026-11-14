import { z } from 'zod'
import { UserSchema } from './schemas'

export const isMockMode = import.meta.env.VITE_ENABLE_MSW === 'true'
  || (import.meta.env.MODE === 'test' && import.meta.env.VITE_ENABLE_MSW !== 'false')
const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const SessionSchema = z.object({ user: UserSchema, csrfToken: z.string().min(1) })

export async function authRequest(
  action: 'login' | 'register' | 'session' | 'logout',
  body?: { email: string; password: string; name?: string },
  csrfToken?: string | null,
) {
  const origin = BASE_URL || window.location.origin
  const response = await fetch(`${origin}/api/auth/${action}`, {
    method: action === 'session' ? 'GET' : 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
  const data: unknown = await response.json().catch(() => null)
  if (action === 'session' && response.status === 401) return null
  if (!response.ok) {
    const error = z.object({ message: z.string() }).safeParse(data)
    throw new Error(error.success ? error.data.message : 'Не удалось выполнить вход. Повторите попытку')
  }
  if (action === 'logout') return null
  return SessionSchema.parse(data)
}
