import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type FailureMode = 'off' | 'always' | 'random'

interface DevState {
  failureMode: FailureMode
  latencyOverrideMs: number | null
  setFailureMode: (mode: FailureMode) => void
  setLatencyOverride: (ms: number | null) => void
}

export const useDevStore = create<DevState>()(
  persist(
    (set) => ({
      failureMode: 'off',
      latencyOverrideMs: null,
      setFailureMode: (failureMode) => set({ failureMode }),
      setLatencyOverride: (latencyOverrideMs) => set({ latencyOverrideMs }),
    }),
    { name: 'ai-buddy-dev' },
  ),
)
