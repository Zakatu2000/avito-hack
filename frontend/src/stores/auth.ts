import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { authRequest, isMockMode } from '../api/auth'

interface AuthState {
  userId: string | null
  csrfToken: string | null
  ready: boolean
  error: string | null
  login: (userId: string) => void
  signIn: (email: string, password: string, name?: string) => Promise<void>
  initialize: () => Promise<void>
  logout: () => Promise<void>
}

const initializer = (mockMode: boolean): import('zustand').StateCreator<AuthState> => (set, get) => ({
  userId: null,
  csrfToken: null,
  ready: mockMode,
  error: null,
  login: (userId) => { if (mockMode) set({ userId }) },
  signIn: async (email, password, name) => {
    const session = await authRequest(name === undefined ? 'login' : 'register', {
      email, password, ...(name === undefined ? {} : { name }),
    })
    if (session) set({ userId: session.user.id, csrfToken: session.csrfToken, ready: true, error: null })
  },
  initialize: async () => {
    if (mockMode) return
    set({ ready: false, error: null })
    try {
      const session = await authRequest('session')
      set({ userId: session?.user.id ?? null, csrfToken: session?.csrfToken ?? null, ready: true })
    } catch {
      set({ error: 'Не удалось проверить вход. Проверьте соединение и повторите попытку', ready: false })
    }
  },
  logout: async () => {
    if (!mockMode) await authRequest('logout', undefined, get().csrfToken)
    set({ userId: null, csrfToken: null })
  },
})

// Only the explicitly selected mock mode persists a synthetic user id.
// Real authentication is restored from the server's HttpOnly session cookie.
export function createAuthStore(mockMode: boolean) {
  return mockMode
    ? create<AuthState>()(persist(initializer(true), { name: 'ai-buddy-auth', partialize: (state) => ({ userId: state.userId }) }))
    : create<AuthState>()(initializer(false))
}

export const useAuthStore = createAuthStore(isMockMode)
