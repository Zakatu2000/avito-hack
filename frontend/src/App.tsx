import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { DevPanel } from './components/DevPanel'
import { AppShell } from './components/layout/AppShell'
import { ToastPort } from './components/ui/Toast'
import { useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'
import { AccessFormPage } from './pages/AccessFormPage'
import { ChatPage } from './pages/ChatPage'
import { ContactsPage } from './pages/ContactsPage'
import { DesignPage } from './pages/DesignPage'
import { HomePage } from './pages/HomePage'
import { KbPage } from './pages/KbPage'
import { LeaveFormPage } from './pages/LeaveFormPage'
import { LoginPage } from './pages/LoginPage'
import { MetricsPage } from './pages/MetricsPage'
import { RequestsPage } from './pages/RequestsPage'
import { TeamPage } from './pages/TeamPage'
import { TimelinePage } from './pages/TimelinePage'
import type { ReactElement } from 'react'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false },
  },
})

function RequireAuth({ children }: { children: ReactElement }) {
  const userId = useAuthStore((s) => s.userId)
  if (!userId) return <Navigate to="/login" replace />
  return children
}

function ThemeSync() {
  const theme = useThemeStore((s) => s.theme)
  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])
  return null
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeSync />
      <BrowserRouter>
        <ToastPort />
        <DevPanel />
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route path="/" element={<HomePage />} />
            <Route path="/timeline" element={<TimelinePage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/requests" element={<RequestsPage />} />
            <Route path="/requests/new/leave" element={<LeaveFormPage />} />
            <Route path="/requests/new/access" element={<AccessFormPage />} />
            <Route path="/contacts" element={<ContactsPage />} />
            <Route path="/kb" element={<KbPage />} />
            <Route path="/team" element={<TeamPage />} />
            <Route path="/metrics" element={<MetricsPage />} />
            <Route path="/design" element={<DesignPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
