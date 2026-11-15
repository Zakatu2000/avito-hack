import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { handlers, resetMockChats } from '../src/mocks/handlers'
import { resetDb } from '../src/mocks/db'
import { useAuthStore } from '../src/stores/auth'
import { useChatStore } from '../src/stores/chat'
import { useDevStore } from '../src/stores/dev'

export const server = setupServer(...handlers)

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
  useDevStore.setState({ failureMode: 'off', latencyOverrideMs: 0 })
})

afterEach(() => {
  cleanup()
  server.resetHandlers()
  localStorage.clear()
  resetDb()
  resetMockChats()
  useAuthStore.setState({ userId: null })
  useChatStore.getState().reset()
  useDevStore.setState({ failureMode: 'off', latencyOverrideMs: 0 })
})

afterAll(() => server.close())
