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
  userId: string | null
  activeId: string | null
  selectChat: (userId: string, activeId: string | null) => void
  activate: (activeId: string) => void
  hydrate: (userId: string, activeId: string, messages: ChatMessage[]) => void
  changeMessage: (id: string, patch: Partial<ChatMessage>) => void
  append: (message: ChatMessage) => void
  reset: () => void
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: [],
      userId: null,
      activeId: null,
      selectChat: (userId, activeId) => set({ userId, activeId, messages: [] }),
      activate: (activeId) => set({ activeId }),
      hydrate: (userId, activeId, messages) => set((state) =>
        state.userId === userId && state.activeId === activeId ? { messages } : state),
      changeMessage: (id, patch) => set((state) => ({
        messages: state.messages.map((message) => message.id === id ? { ...message, ...patch } : message),
      })),
      append: (message) => set((state) => ({ messages: [...state.messages, message] })),
      reset: () => set({ messages: [], userId: null, activeId: null }),
    }),
    {
      name: 'ai-buddy-chat', version: 2,
      migrate: () => ({}),
      partialize: (state) => ({
        messages: isMockMode ? state.messages : [],
        userId: state.userId,
        activeId: state.activeId,
      }),
    },
  ),
)
