export async function enableApiMock(): Promise<void> {
  if (import.meta.env.MODE === 'test') return
  if (import.meta.env.VITE_ENABLE_MSW !== 'true') return
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return
  const { worker } = await import('./mswWorker')
  await worker.start({ onUnhandledRequest: 'bypass' })
}
