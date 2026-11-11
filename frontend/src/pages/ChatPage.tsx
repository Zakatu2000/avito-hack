import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { getErrorMessage } from '../api/client'
import { useContacts, useSendChatMessage } from '../api/hooks'
import type { ChatAction } from '../api/schemas'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { toast } from '../components/ui/Toast'
import { useChatStore } from '../stores/chat'

const WELCOME =
  'Привет! Я AI-buddy — детерминированный прототип без ИИ. Знаю про отгулы, доступы, чек-лист адаптации, контакты и документы. Спроси коротко — например: «как оформить отгул?»'

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
  const messages = useChatStore((s) => s.messages)
  const typing = useChatStore((s) => s.typing)
  const addUser = useChatStore((s) => s.addUser)
  const addBot = useChatStore((s) => s.addBot)
  const markLastFailed = useChatStore((s) => s.markLastFailed)
  const setTyping = useChatStore((s) => s.setTyping)
  const lastUserMessage = useChatStore((s) => s.lastUserMessage)
  const sendChat = useSendChatMessage()
  const [draft, setDraft] = useState('')
  const logRef = useRef<HTMLDivElement>(null)
  const greeted = useRef(false)

  useEffect(() => {
    if (messages.length === 0 && !greeted.current) {
      greeted.current = true
      addBot({ id: 'welcome', text: WELCOME })
    }
  }, [messages.length, addBot])

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight })
  }, [messages.length, typing])

  const send = (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || sendChat.isPending) return
    addUser(trimmed)
    setDraft('')
    setTyping(true)
    sendChat.mutate(trimmed, {
      onSuccess: (reply) => {
        addBot({ id: `bot-${Date.now()}`, text: reply.text, actions: reply.actions })
        setTyping(false)
      },
      onError: (err) => {
        markLastFailed()
        setTyping(false)
        toast(getErrorMessage(err, 'Бот не ответил'), 'error')
      },
    })
  }

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="heading-l">
            Чат с <span className="hl hl-green">AI-buddy</span>
          </h1>
          <p className="body-secondary" style={{ marginTop: 4 }}>
            Детерминированный бот-имитация: интенты и ключевые слова, без ИИ
          </p>
        </div>
      </div>

      <div className="chat" style={{ maxWidth: 720 }}>
        <div className="chat__log" ref={logRef} aria-live="polite" aria-label="История сообщений">
          {messages.map((msg) => (
            <div key={msg.id} className={`msg msg--${msg.role}`}>
              {msg.text}
              {msg.failed && (
                <div className="msg__failed" role="alert">
                  <span>Не доставлено</span>
                  {lastUserMessage && (
                    <Button size="s" variant="secondary" onClick={() => send(lastUserMessage)}>
                      Повторить
                    </Button>
                  )}
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
            <Button key={s} size="s" variant="secondary" onClick={() => send(s)} disabled={sendChat.isPending}>
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
          <Button type="submit" loading={sendChat.isPending}>
            Отправить
          </Button>
        </form>
      </div>
    </div>
  )
}
