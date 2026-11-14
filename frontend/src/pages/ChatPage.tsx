import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getErrorMessage } from '../api/client'
import { useContacts, useSendChatMessage } from '../api/hooks'
import type { ChatAction } from '../api/schemas'
import { service } from '../services'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { toast } from '../components/ui/Toast'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'

const WELCOME =
  'Привет! Я AI-buddy. Знаю про отгулы, доступы, чек-лист адаптации, контакты и документы. Спроси коротко — например: «как оформить отгул?»'

const SUGGESTIONS = [
  'Как оформить отгул?',
  'Нужен доступ к Jira',
  'Что дальше по плану?',
  'К кому обратиться?',
  'Где документы?',
]

function ActionCards({ actions }: { actions: ChatAction[] }) {
  const contacts = useContacts()
  if (actions.length === 0) return null
  return (
    <div className="msg__actions">
      {actions.map((action) => {
        if (action.kind === 'navigate' && action.target) {
          return (
            <Link key={action.id} to={action.target} className="btn btn--s btn--primary">
              {action.label}
            </Link>
          )
        }
        const contact = contacts.data?.find((c) => c.id === action.target)
        if (!contact) return null
        return (
          <div key={action.id} className="msg__contact">
            <strong>{contact.name}</strong> · {contact.role}
            <br />
            {contact.channel} · {contact.responseTime}
          </div>
        )
      })}
    </div>
  )
}

export function ChatPage() {
  const authUserId = useAuthStore((s) => s.userId)
  const activeId = useChatStore((s) => s.activeId)
  const messages = useChatStore((s) => s.messages)
  const typing = useChatStore((s) => s.typing)
  const addUser = useChatStore((s) => s.addUser)
  const addBot = useChatStore((s) => s.addBot)
  const markLastFailed = useChatStore((s) => s.markLastFailed)
  const setTyping = useChatStore((s) => s.setTyping)
  const queryClient = useQueryClient()
  const sendChat = useSendChatMessage()
  const [draft, setDraft] = useState('')
  const logRef = useRef<HTMLDivElement>(null)
  const greeted = useRef(false)

  const chatsQuery = useQuery({
    queryKey: ['chats'],
    queryFn: () => service.listChats(),
    enabled: !!authUserId,
  })
  const historyQuery = useQuery({
    queryKey: ['chat-messages', activeId],
    queryFn: () => service.getChatMessages(activeId!),
    enabled: !!authUserId && !!activeId,
  })
  const deleteChat = useMutation({
    mutationFn: (id: string) => service.deleteChat(id),
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({ queryKey: ['chats'] })
      if (id === activeId && authUserId) useChatStore.getState().selectChat(authUserId, null)
      toast('Чат удалён', 'success')
    },
    onError: (err) => toast(getErrorMessage(err, 'Не удалось удалить чат'), 'error'),
  })
  const createChat = useMutation({
    mutationFn: () => service.createChat(),
    onSuccess: (chat) => {
      if (!authUserId) return
      greeted.current = false
      useChatStore.getState().selectChat(authUserId, chat.id)
      void queryClient.invalidateQueries({ queryKey: ['chats'] })
    },
    onError: (err) => toast(getErrorMessage(err, 'Не удалось создать чат'), 'error'),
  })

  // Чужой или устаревший локальный кеш не показываем: чаты привязаны к аккаунту.
  useEffect(() => {
    if (!authUserId) return
    const store = useChatStore.getState()
    if (store.userId !== authUserId) store.selectChat(authUserId, null)
  }, [authUserId])

  // Если активный чат был удалён в другой вкладке, история вернёт 404.
  useEffect(() => {
    if (!authUserId || !activeId || !historyQuery.isError) return
    if ((historyQuery.error as { status?: number } | null)?.status === 404) {
      useChatStore.getState().selectChat(authUserId, null)
    }
  }, [authUserId, activeId, historyQuery.isError, historyQuery.error])

  // История живёт на сервере: подставляем её при открытии чата (в т.ч. после F5).
  useEffect(() => {
    if (!authUserId || !activeId || !historyQuery.data) return
    useChatStore.getState().hydrate(
      authUserId,
      activeId,
      historyQuery.data.map((m) => ({ id: String(m.id), role: m.role, text: m.text, actions: m.actions })),
    )
  }, [authUserId, activeId, historyQuery.data])

  useEffect(() => {
    const emptyConversation = !activeId || (historyQuery.isSuccess && historyQuery.data.length === 0)
    if (emptyConversation && messages.length === 0 && !greeted.current) {
      greeted.current = true
      addBot({ id: 'welcome', text: WELCOME })
    }
    if (messages.length > 0) greeted.current = true
  }, [activeId, historyQuery.isSuccess, historyQuery.data, messages.length, addBot])

  useEffect(() => {
    const el = logRef.current
    if (el && typeof el.scrollTo === 'function') el.scrollTo({ top: el.scrollHeight })
  }, [messages.length, typing])

  const openChat = (chatId: string | null) => {
    if (!authUserId) return
    greeted.current = false
    useChatStore.getState().selectChat(authUserId, chatId)
  }

  const send = async (text: string, retry = false) => {
    const trimmed = text.trim()
    if (!trimmed || sendChat.isPending || createChat.isPending || typing) return
    setDraft('')
    setTyping(true)
    let userAdded = false
    try {
      // Allocate the persistent conversation before sending. A provider 503 can
      // then be retried in the same thread instead of orphaning the user turn.
      let conversationId = activeId
      if (!conversationId) {
        const chat = await service.createChat(trimmed.slice(0, 60))
        conversationId = chat.id
        if (authUserId) useChatStore.getState().selectChat(authUserId, conversationId)
        void queryClient.invalidateQueries({ queryKey: ['chats'] })
      }
      if (!retry) {
        addUser(trimmed)
        userAdded = true
      }
      const reply = await sendChat.mutateAsync({ message: trimmed, conversationId })
      if (reply.conversationId) useChatStore.getState().activate(reply.conversationId)
      addBot({ id: `bot-${Date.now()}`, text: reply.text, actions: reply.actions })
    } catch (err) {
      if (!retry && !userAdded) addUser(trimmed)
      markLastFailed()
      toast(getErrorMessage(err, 'Бот не ответил'), 'error')
    } finally {
      setTyping(false)
    }
  }

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="heading-l">
            Чат с <span className="hl hl-green">AI-buddy</span>
          </h1>
          <p className="body-secondary" style={{ marginTop: 4 }}>
            Отвечает по данным твоего онбординга; история чатов сохраняется
          </p>
        </div>
      </div>

      <div className="chat-layout">
        <aside className="chat-list" aria-label="Список чатов">
          <Button
            size="s"
            variant="primary"
            onClick={() => createChat.mutate()}
            loading={createChat.isPending}
            disabled={createChat.isPending || sendChat.isPending || typing}
          >
            + Новый чат
          </Button>
          <div className="chat-list__items">
            {(chatsQuery.data ?? []).map((chat) => (
              <div
                key={chat.id}
                className={`chat-list__item${chat.id === activeId ? ' chat-list__item--active' : ''}`}
              >
                <button
                  type="button"
                  className="chat-list__open"
                  onClick={() => openChat(chat.id)}
                  title={chat.title}
                  disabled={sendChat.isPending || createChat.isPending || typing}
                >
                  {chat.title}
                </button>
                <button
                  type="button"
                  className="chat-list__delete"
                  aria-label={`Удалить чат «${chat.title}»`}
                  title="Удалить чат"
                  onClick={() => deleteChat.mutate(chat.id)}
                  disabled={deleteChat.isPending || (chat.id === activeId && (sendChat.isPending || createChat.isPending || typing))}
                >
                  ×
                </button>
              </div>
            ))}
            {chatsQuery.data?.length === 0 && (
            <p className="chat-list__empty">Чатов пока нет — начни с вопроса ниже.</p>
            )}
            {chatsQuery.isError && (
              <div role="alert" className="chat-list__empty">
                Не удалось загрузить список чатов.{' '}
                <button type="button" className="chat-list__open" onClick={() => void chatsQuery.refetch()}>
                  Повторить
                </button>
              </div>
            )}
          </div>
        </aside>

        <div className="chat" style={{ flex: 1, minWidth: 0 }}>
          {historyQuery.isError && activeId && (historyQuery.error as { status?: number } | null)?.status !== 404 && (
            <div role="alert" className="msg__failed">
              Не удалось загрузить историю чата.{' '}
              <Button size="s" variant="secondary" onClick={() => void historyQuery.refetch()}>
                Повторить
              </Button>
            </div>
          )}
          <div className="chat__log" ref={logRef} aria-live="polite" aria-label="История сообщений">
            {messages.map((msg) => (
              <div key={msg.id} className={`msg msg--${msg.role}`}>
                {msg.text}
                {msg.failed && (
                  <div className="msg__failed" role="alert">
                    <span>Не доставлено</span>
                    <Button
                      size="s"
                      variant="secondary"
                      onClick={() => send(msg.text, true)}
                      disabled={sendChat.isPending || createChat.isPending || typing}
                    >
                      Повторить
                    </Button>
                  </div>
                )}
                {msg.role === 'bot' && msg.actions && msg.actions.length > 0 && (
                  <ActionCards actions={msg.actions} />
                )}
              </div>
            ))}
            {typing && (
              <div className="typing" aria-label="AI-buddy печатает">
                <span className="typing__dot" />
                <span className="typing__dot" />
                <span className="typing__dot" />
              </div>
            )}
          </div>

          <div className="chat__suggestions" aria-label="Подсказки">
            {SUGGESTIONS.map((s) => (
              <Button
                key={s}
                size="s"
                variant="secondary"
                onClick={() => send(s)}
                disabled={sendChat.isPending || createChat.isPending || typing}
              >
                {s}
              </Button>
            ))}
          </div>

          <form
            className="chat__form"
            onSubmit={(e) => {
              e.preventDefault()
              send(draft)
            }}
          >
            <Input
              name="chat-message"
              aria-label="Сообщение боту"
              placeholder="Спроси про отгул, доступы, план…"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={500}
            />
            <Button type="submit" loading={sendChat.isPending || createChat.isPending || typing}>
              Отправить
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
