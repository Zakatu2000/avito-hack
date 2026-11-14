import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { isMockMode } from '../api/auth'
import type { ChatAction, KnowledgeHit } from '../api/schemas'

export interface ChatMessage {
  id: string
  role: 'user' | 'bot'
  text: string
  taskId?: string
  actions?: ChatAction[]
  sources?: KnowledgeHit[]
  answerMethod?: 'rules' | 'model'
  replyId?: string
  feedback?: 'resolved' | 'mentor'
  failed?: string
}

interface ChatState {
  messages: ChatMessage[]
  changeMessage: (id: string, patch: Partial<ChatMessage>) => void
  append: (message: ChatMessage) => void
  reset: () => void
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: [],
      changeMessage: (id, patch) => set((state) => ({
        messages: state.messages.map((message) => message.id === id ? { ...message, ...patch } : message),
      })),
      append: (message) => set((state) => ({ messages: [...state.messages, message] })),
      reset: () => set({ messages: [] }),
    }),
    {
      name: 'ai-buddy-chat', version: 1,
      migrate: () => ({}),
      partialize: (state) => ({ messages: isMockMode ? state.messages : [] }),
    },
  ),
)
