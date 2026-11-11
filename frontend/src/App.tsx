import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { DesignPage } from './pages/DesignPage'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/design" element={<DesignPage />} />
        <Route path="*" element={<Navigate to="/design" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
