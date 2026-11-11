import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ChatAction } from '../api/schemas'

export interface ChatMessage {
  id: string
  role: 'user' | 'bot'
  text: string
  actions?: ChatAction[]
  failed?: boolean
}

interface ChatState {
  messages: ChatMessage[]
  typing: boolean
  lastUserMessage: string | null
  addUser: (text: string) => ChatMessage
  addBot: (msg: Omit<ChatMessage, 'role'>) => void
  markLastFailed: () => void
  setTyping: (typing: boolean) => void
  reset: () => void
}

function makeId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `m-${Date.now()}-${Math.round(Math.random() * 1e6)}`
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      messages: [],
      typing: false,
      lastUserMessage: null,
      addUser: (text) => {
        const msg: ChatMessage = { id: makeId(), role: 'user', text }
        set({ messages: [...get().messages, msg], lastUserMessage: text })
        return msg
      },
      addBot: (msg) => set({ messages: [...get().messages, { ...msg, role: 'bot' }] }),
      markLastFailed: () => {
        const messages = [...get().messages]
        for (let i = messages.length - 1; i >= 0; i--) {
          if (messages[i].role === 'user') {
            messages[i] = { ...messages[i], failed: true }
            break
          }
        }
        set({ messages })
      },
      setTyping: (typing) => set({ typing }),
      reset: () => set({ messages: [], typing: false, lastUserMessage: null }),
    }),
    { name: 'ai-buddy-chat' },
  ),
)
