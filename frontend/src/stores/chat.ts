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
  /** Владелец закешированной истории: чужой кеш не показываем. */
  userId: string | null
  /** Активный серверный чат; null — временный черновик до первого сообщения. */
  activeId: string | null
  messages: ChatMessage[]
  typing: boolean
  lastUserMessage: string | null
  /** Переключиться на чат; смена пользователя или чата очищает локальный список. */
  selectChat: (userId: string, chatId: string | null) => void
  /** Привязать серверный id к уже открытому (только что созданному) чату. */
  activate: (chatId: string) => void
  /** Подменить список сообщений серверной историей активного чата. */
  hydrate: (userId: string, chatId: string | null, messages: ChatMessage[]) => void
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

const EMPTY = { activeId: null, messages: [], typing: false, lastUserMessage: null }

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      userId: null,
      ...EMPTY,
      selectChat: (userId, chatId) => {
        const state = get()
        if (state.userId !== userId) {
          set({ userId, ...EMPTY, activeId: chatId })
          return
        }
        if (state.activeId !== chatId) {
          set({ ...EMPTY, activeId: chatId })
        }
      },
      activate: (chatId) => set({ activeId: chatId }),
      hydrate: (userId, chatId, messages) => {
        const state = get()
        if (state.userId !== userId || state.activeId !== chatId || state.typing
            || state.messages.length > 0) return
        set({ messages, lastUserMessage: null })
      },
      addUser: (text) => {
        const msg: ChatMessage = { id: makeId(), role: 'user', text }
        set({ messages: [...get().messages, msg], lastUserMessage: text })
        return msg
      },
      addBot: (msg) => {
        const messages = [...get().messages]
        for (let i = messages.length - 1; i >= 0; i--) {
          if (messages[i].role === 'user') {
            if (messages[i].failed) messages[i] = { ...messages[i], failed: false }
            break
          }
        }
        set({
          messages: [...messages, { ...msg, role: 'bot' }],
          lastUserMessage: null,
        })
      },
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
      reset: () => set({ userId: null, ...EMPTY }),
    }),
    {
      name: 'ai-buddy-chat',
      partialize: (state) => ({
        userId: state.userId,
        activeId: state.activeId,
      }),
    },
  ),
)
