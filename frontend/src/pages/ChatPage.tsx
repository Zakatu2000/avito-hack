import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { useAdaptationPlan, useChatConfig, useChatFeedback, usePortalChat } from '../api/adaptation'
import { isMockMode } from '../api/auth'
import { getErrorMessage } from '../api/client'
import { useContacts } from '../api/hooks'
import type { ChatAction } from '../api/schemas'
import { Button } from '../components/ui/Button'
import { Textarea } from '../components/ui/Input'
import { service } from '../services'
import { useAuthStore } from '../stores/auth'
import { useChatStore, type ChatMessage } from '../stores/chat'

const EMPTY_MESSAGES: ChatMessage[] = []

const SUGGESTIONS = [
  'Как оформить отгул?', 'Нужен доступ к Jira', 'Что дальше по плану?',
  'К кому обратиться?', 'Где документы?',
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


function Feedback({ message }: { message: ChatMessage }) {
  const feedback = useChatFeedback()
  const change = useChatStore((state) => state.changeMessage)
  if (!message.replyId) return null
  if (message.feedback) return <p className="caption" role="status">Отзыв сохранён</p>
  return <div className="msg__actions">
    {(['resolved', 'mentor'] as const).map((outcome) => <Button key={outcome} size="s" variant="secondary"
      disabled={feedback.isPending} onClick={() => {
        if (message.replyId) feedback.mutate({ messageId: message.replyId, outcome }, {
          onSuccess: () => change(message.id, { feedback: outcome }),
        })
      }}>{outcome === 'resolved' ? 'Решено' : 'Нужен наставник'}</Button>)}
    {feedback.isError && <span role="alert">{getErrorMessage(feedback.error)}</span>}
  </div>
}

export function ChatPage() {
  const userId = useAuthStore((state) => state.userId)
  const chatOwner = useChatStore((state) => state.userId)
  const activeId = useChatStore((state) => state.activeId)
  const storedMessages = useChatStore((state) => state.messages)
  const messages = isMockMode || chatOwner === userId ? storedMessages : EMPTY_MESSAGES
  const conversationId = chatOwner === userId ? activeId ?? undefined : undefined
  const cache = useQueryClient()
  const change = useChatStore((state) => state.changeMessage)
  const append = useChatStore((state) => state.append)
  const config = useChatConfig()
  const plan = useAdaptationPlan()
  const sendChat = usePortalChat()
  const [params, setParams] = useSearchParams()
  const taskId = params.get('task') || undefined
  const task = plan.data?.items.find((item) => item.id === taskId)
  const [draft, setDraft] = useState(taskId ? 'Помоги выполнить этот шаг' : '')
  const field = useRef<HTMLTextAreaElement>(null)
  const log = useRef<HTMLDivElement>(null)
  const follow = useRef(true)
  const pending = useRef(false)
  const composing = useRef(false)
  const maxLength = isMockMode ? 500 : 4000
  const chats = useQuery({
    queryKey: ['chats', userId],
    queryFn: service.listChats,
    enabled: !isMockMode && !!userId,
  })
  const history = useQuery({
    queryKey: ['chat-messages', userId, conversationId],
    queryFn: () => service.getChatMessages(conversationId!),
    enabled: !isMockMode && !!userId && !!conversationId,
    refetchOnWindowFocus: false,
    staleTime: Infinity,
  })
  const refreshChats = () => void cache.invalidateQueries({ queryKey: ['chats', userId] })
  const removeChat = useMutation({
    mutationFn: service.deleteChat,
    onSuccess: (_reply, id) => {
      if (useAuthStore.getState().userId !== userId) return
      if (userId && id === useChatStore.getState().activeId) {
        useChatStore.getState().selectChat(userId, null)
      }
      cache.removeQueries({ queryKey: ['chat-messages', userId, id] })
      refreshChats()
    },
  })
  const selectChat = (id: string | null) => {
    if (!userId) return
    if (id) void cache.invalidateQueries({ queryKey: ['chat-messages', userId, id] })
    setDraft('')
    follow.current = true
    useChatStore.getState().selectChat(userId, id)
  }

  useLayoutEffect(() => {
    if (!isMockMode && userId && chatOwner !== userId) {
      useChatStore.getState().selectChat(userId, null)
    }
  }, [userId, chatOwner])

  useEffect(() => {
    if (!history.data || !userId || !conversationId) return
    useChatStore.getState().hydrate(userId, conversationId, history.data.map((entry) => ({
      id: String(entry.id), role: entry.role, text: entry.text, actions: entry.actions,
      sources: entry.sources, answerMethod: entry.answerMethod, replyId: entry.messageId,
      feedback: entry.feedback,
    })))
  }, [history.data, history.dataUpdatedAt, userId, conversationId])

  useEffect(() => {
    if (userId && conversationId && (history.error as { status?: number } | null)?.status === 404) {
      useChatStore.getState().selectChat(userId, null)
    }
  }, [history.error, userId, conversationId])


  useLayoutEffect(() => {
    const input = field.current
    if (!input) return
    input.style.height = 'auto'
    input.style.height = input.scrollHeight + 'px'
  }, [draft])

  useEffect(() => {
    if (log.current && follow.current) log.current.scrollTop = log.current.scrollHeight
  }, [messages, sendChat.isPending])

  const send = (text: string, retry?: ChatMessage) => {
    const message = text.trim()
    if (!message || message.length > maxLength || (pending.current || history.isFetching)) return
    pending.current = true
    const id = retry?.id ?? (globalThis.crypto?.randomUUID?.() ?? 'message-' + Date.now() + '-' + Math.random().toString(36).slice(2))
    const context = retry ? retry.taskId : taskId
    if (retry) change(id, { failed: undefined })
    else {
      append({ id, role: 'user', text: message, taskId: context })
      setDraft('')
    }
    follow.current = true
    sendChat.mutate({ message, messageId: id, taskId: context, conversationId }, {
      onSuccess: (reply) => {
        if (useAuthStore.getState().userId !== userId) return
        if (!isMockMode && reply.conversationId) {
          useChatStore.getState().activate(reply.conversationId)
          void cache.invalidateQueries({ queryKey: ['chat-messages', userId, reply.conversationId] })
          refreshChats()
        }
        append({ id: 'reply-' + id, role: 'bot', text: reply.text, actions: reply.actions,
          sources: reply.sources, answerMethod: reply.answerMethod, replyId: reply.messageId })
      },
      onError: (err) => {
        if (useAuthStore.getState().userId === userId) change(id, { failed: getErrorMessage(err, 'Помощник не ответил') })
      },
      onSettled: () => { pending.current = false },
    })
  }

  const mode = isMockMode ? 'Учебный режим · локальный сценарий' : config.data?.aiMode === 'live'
    ? 'ИИ подключён · часть ответов по правилам' : config.data?.aiMode === 'demo' ? 'Демо · ответы по правилам' : undefined
  return <div className="page chat-page">
    <div className="page__head"><div>
      <h1 className="heading-l">Чат с <span className="hl hl-green">AI-buddy</span></h1>
      {mode && <p className="body-secondary">{mode}</p>}
    </div></div>
    <div className="chat-layout">
    {!isMockMode && <aside className="chat-list" aria-label="Список чатов">
      <Button size="s" onClick={() => selectChat(null)} disabled={sendChat.isPending}>+ Новый чат</Button>
      <div className="chat-list__items">
        {chats.data?.map((chat) => <div key={chat.id}
          className={'chat-list__item' + (chat.id === conversationId ? ' chat-list__item--active' : '')}>
          <button type="button" className="chat-list__open" onClick={() => selectChat(chat.id)}
            disabled={sendChat.isPending}>{chat.title}</button>
          <button type="button" className="chat-list__delete" aria-label={'Удалить чат «' + chat.title + '»'}
            onClick={() => removeChat.mutate(chat.id)} disabled={removeChat.isPending || sendChat.isPending}>×</button>
        </div>)}
        {chats.isError && <p role="alert">Не удалось загрузить список чатов.{' '}
          <button type="button" onClick={() => void chats.refetch()}>Повторить</button></p>}
        {removeChat.isError && <p role="alert">{getErrorMessage(removeChat.error, 'Не удалось удалить чат')}</p>}
      </div>
    </aside>}
    <section className="chat" aria-label="AI-buddy">
      {history.isError && <p role="alert">Не удалось загрузить историю.{' '}
        <button type="button" onClick={() => void history.refetch()}>Повторить</button></p>}
      <div className="chat__log" ref={log} role="log" aria-label="История сообщений" aria-live="polite"
        tabIndex={0} onScroll={(event) => {
          const el = event.currentTarget
          follow.current = el.scrollHeight - el.scrollTop - el.clientHeight < 64
        }}>
        {!messages.length && <div className="msg msg--bot">Привет! Помогу с доступами, заявками, обучением и твоим планом адаптации.</div>}
        {messages.map((msg) => <div key={msg.id} className={'msg msg--' + msg.role}>
          <div className="msg__text">{msg.text}</div>
          {msg.failed && <div className="msg__failed">
            <span role="alert">{msg.failed}</span>
            <Button size="s" variant="secondary" disabled={sendChat.isPending} onClick={() => send(msg.text, msg)}>Повторить</Button>
          </div>}
          {msg.actions && <ActionCards actions={msg.actions} />}
          {!!msg.sources?.length && <ul className="chat-sources">{msg.sources.map((source) => (
            <li key={source.chunkId}>{source.url ? <a href={source.url} target="_blank" rel="noreferrer">{source.title}</a> : source.title}
              {' · '}{source.synthetic ? 'учебный пример' : source.sourceLocator ?? source.section}</li>
          ))}</ul>}
          {msg.answerMethod && <p className="caption">{msg.answerMethod === 'model' ? 'Ответ с ИИ' : 'Ответ по правилам'}</p>}
          <Feedback message={msg} />
        </div>)}
        {sendChat.isPending && <div className="typing" role="status">AI-buddy готовит ответ…</div>}
      </div>
      {taskId && <div className="page__actions chat__context"><span>Задача: {task?.title ?? taskId}</span>
        <Button size="s" variant="secondary" onClick={() => setParams({})}>Убрать задачу</Button></div>}
      <div className="chat__suggestions" aria-label="Подсказки">
        {SUGGESTIONS.map((suggestion) => <Button key={suggestion} size="s" variant="secondary" onClick={() => send(suggestion)} disabled={sendChat.isPending || history.isFetching}>{suggestion}</Button>)}
      </div>
      <form className="chat__form" onSubmit={(event) => { event.preventDefault(); send(draft) }}>
        <Textarea ref={field} rows={2} name="chat-message" aria-label="Сообщение боту"
          placeholder="Напишите сообщение" value={draft} maxLength={maxLength}
          onChange={(event) => setDraft(event.target.value)}
          onCompositionStart={() => { composing.current = true }}
          onCompositionEnd={() => { composing.current = false }}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey && !composing.current && !event.nativeEvent.isComposing && event.keyCode !== 229) {
              event.preventDefault(); send(draft)
            }
          }} />
        <Button type="submit" loading={sendChat.isPending} disabled={!draft.trim() || history.isFetching}>Отправить</Button>
      </form>
    </section>
    </div>
  </div>
}
