import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { App } from '../src/App'
import { ToastPort } from '../src/components/ui/Toast'
import { useAuthStore } from '../src/stores/auth'

export type TestRole = 'intern' | 'intern2' | 'mentor' | 'lead'

const ROLE_USER: Record<TestRole, string> = {
  intern: 'u-intern-1',
  intern2: 'u-intern-2',
  mentor: 'u-mentor-1',
  lead: 'u-lead-1',
}

export function loginAs(role: TestRole) {
  useAuthStore.setState({ userId: ROLE_USER[role] })
}

export function renderWithProviders(ui: ReactElement, { route = '/' }: { route?: string } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastPort />
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

export function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastPort />
      <App />
    </QueryClientProvider>,
  )
}
