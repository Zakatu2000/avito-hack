import { useDevStore } from '../stores/dev'

export async function simulateLatency(): Promise<void> {
  const { latencyOverrideMs } = useDevStore.getState()
  const ms = latencyOverrideMs ?? 300 + Math.round(Math.random() * 900)
  await new Promise((resolve) => setTimeout(resolve, ms))
}

export function shouldSimulateFailure(): boolean {
  const { failureMode } = useDevStore.getState()
  if (failureMode === 'always') return true
  if (failureMode === 'random') return Math.random() < 0.5
  return false
}
