import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { isMockMode } from '../api/auth'
import { useContacts, useMe } from '../api/hooks'
import type { Contact } from '../api/schemas'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input, Textarea } from '../components/ui/Input'
import { SkeletonCard } from '../components/ui/Skeleton'
import { ErrorState } from '../components/ui/States'
import { actionsForTopic, HELP_TOPICS, matchContacts, matchHelpTopics, messageTemplate, type HelpTopic } from '../utils/contactRouting'
import './ContactsPage.css'

interface Draft {
  recipient: string
  text: string
}

function ContactCard({ contact, prepare }: { contact: Contact; prepare: (draft: Draft, trigger: HTMLElement) => void }) {
  const initials = contact.name.split(/\s+/).slice(0, 2).map((word) => word[0]).join('')
  return <article className="contact-person">
    <div className="contact-person__identity">
      <span aria-hidden="true" className={'contact-person__avatar contact-person__avatar--' + contact.tone}>{initials}</span>
      <div>
        <h3 className="heading-s">{contact.name}</h3>
        <p className="body-secondary">{contact.role}</p>
      </div>
      {contact.source === 'demo' && <span className="contact-note">Демо-контакт</span>}
    </div>
    <ul className="contact-person__topics">{contact.helpsWith.map((topic) => <li key={topic}>{topic}</li>)}</ul>
    <Button size="s" variant="secondary" aria-label={'Подготовить сообщение — ' + contact.name}
      onClick={(event) => prepare({
        recipient: contact.name,
        text: messageTemplate('Хочу обратиться за помощью.'),
      }, event.currentTarget)}>Подготовить сообщение</Button>
  </article>
}

function MessageDraft({ draft, close }: { draft: Draft; close: () => void }) {
  const [text, setText] = useState(draft.text)
  const [status, setStatus] = useState('')
  const input = useRef<HTMLTextAreaElement>(null)
  useEffect(() => { input.current?.focus() }, [])
  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setStatus('Скопировано')
    } catch {
      input.current?.focus()
      input.current?.select()
      setStatus('Буфер недоступен. Текст выделен для ручного копирования.')
    }
  }
  return <Card role="region" className="contact-draft" aria-labelledby="contact-draft-heading">
    <div className="contact-section-head">
      <div><h2 className="heading-s" id="contact-draft-heading">Черновик сообщения</h2><p className="caption">{draft.recipient}</p></div>
      <Button size="s" variant="secondary" onClick={close}>Закрыть черновик</Button>
    </div>
    <Textarea ref={input} name="help-message" label="Текст сообщения" rows={7} value={text}
      onChange={(event) => { setText(event.target.value); setStatus('') }} />
    <div className="contact-actions">
      <Button size="s" disabled={!text.trim()} onClick={() => void copy()}>Скопировать текст</Button>
      <span role="status">{status}</span>
    </div>
  </Card>
}

function Recommendation({ topic, query, contacts, canRequest, prepare }: {
  topic: HelpTopic
  query: string
  contacts: Contact[]
  canRequest: boolean
  prepare: (draft: Draft, trigger: HTMLElement) => void
}) {
  const relevant = contacts.filter((person) => person.roleKey && topic.roles.includes(person.roleKey))
  const mentorMissing = !isMockMode && topic.roles.includes('mentor') && !relevant.length
  const lead = contacts.filter((person) => person.roleKey === 'lead')
  const people = mentorMissing ? lead : relevant
  const actions = actionsForTopic(topic, query)
  const draftRecipient = topic.id === 'support' ? 'Техническая помощь' : people.map((person) => person.name).join(', ') || topic.label
  const needsServer = canRequest && isMockMode && actions.some((action) => action.request === 'server')
  const queue = topic.id === 'first-task' && !mentorMissing
  return <>
    <span className="contact-result__icon" aria-hidden="true">{topic.icon}</span>
    <h2 className="heading-m">{topic.title}</h2>
    <p className="body-secondary">{topic.description}</p>
    {!!people.length && <ul className="contact-result__people">{people.map((person) => (
      <li key={person.id}>{person.name} <span className="caption">· {person.role}{person.source === 'demo' ? ', демо' : ''}</span></li>
    ))}</ul>}
    {queue && relevant.length > 1 && <p className="caption">Запрос увидят наставники вашей команды.</p>}
    {mentorMissing && <p className="caption">{lead.length
      ? 'В команде пока нет наставника. Можно подготовить сообщение руководителю или спросить AI-buddy.'
      : 'В команде пока нет наставника. AI-buddy поможет разобраться со следующим шагом.'}</p>}
    {needsServer && <p className="caption">Для отправки этой заявки подключите сервер портала.</p>}
    <div className="contact-actions">
      {actions.filter((action) => !action.request ||
        (canRequest && (action.request === 'existing' || (!isMockMode && !mentorMissing)))).map((action, index) => (
        <Link key={action.to} className={'btn btn--s btn--' + (index === 0 ? 'primary' : 'secondary')} to={action.to}>{action.label}</Link>
      ))}
      {mentorMissing && <Link className="btn btn--s btn--secondary" to="/chat">Спросить AI-buddy</Link>}
      <Button size="s" variant="secondary" onClick={(event) => prepare({
        recipient: draftRecipient, text: messageTemplate(topic.message),
      }, event.currentTarget)}>Подготовить сообщение</Button>
    </div>
  </>
}

export function ContactsPage() {
  const contacts = useContacts()
  const me = useMe()
  const [query, setQuery] = useState('')
  const [chosen, setChosen] = useState<string>()
  const [draft, setDraft] = useState<(Draft & { version: number })>()
  const draftVersion = useRef(0)
  const trigger = useRef<HTMLElement | null>(null)
  const search = useRef<HTMLInputElement>(null)

  if (contacts.isLoading || me.isLoading) {
    return <div className="page"><SkeletonCard lines={3} /><SkeletonCard lines={3} /></div>
  }
  if (contacts.isError || !contacts.data || me.isError || !me.data) {
    return <ErrorState onRetry={() => { void contacts.refetch(); void me.refetch() }}
      retryLoading={contacts.isRefetching || me.isRefetching} />
  }

  const searching = Boolean(query.trim())
  const matches = searching ? matchHelpTopics(query) : []
  const matchedPeople = searching ? matchContacts(contacts.data, query) : []
  const topic = HELP_TOPICS.find((value) => value.id === chosen) ?? (matches.length === 1 ? matches[0] : undefined)
  let people = contacts.data
  if (matchedPeople.length) {
    people = matchedPeople
  } else if (topic?.roles.length) {
    people = people.filter((person) => person.roleKey && topic.roles.includes(person.roleKey))
    if (!people.length && topic.roles.includes('mentor')) {
      people = contacts.data.filter((person) => person.roleKey === 'lead')
    }
  } else if (searching && !matches.length) {
    people = []
  }
  const canRequest = me.data.role === 'intern'
  const prepare = (value: Draft, button: HTMLElement) => {
    trigger.current = button
    setDraft({ ...value, version: ++draftVersion.current })
  }
  const clear = () => { setQuery(''); setChosen(undefined); search.current?.focus() }

  return <div className="page contacts-page">
    <header className="page__head"><h1 className="heading-l">К кому обратиться</h1></header>

    <div className="contact-navigator">
      <Card className="contact-search">
        <Input ref={search} label="Что случилось?" name="contact-search" type="search" autoComplete="off"
          value={query} placeholder="Например, не работает VPN" maxLength={200}
          onChange={(event) => { setQuery(event.target.value); setChosen(undefined) }} />
        <div className="contact-topics" aria-label="Типовые ситуации" role="group">
          {HELP_TOPICS.map((value) => <Button key={value.id} size="s" variant="secondary" aria-pressed={topic?.id === value.id}
            onClick={() => { setQuery(''); setChosen(value.id) }}>
            <span aria-hidden="true">{value.icon}</span> {value.label}
          </Button>)}
        </div>
        {(searching || chosen) && <Button className="contact-reset" size="s" variant="ghost" onClick={clear}>Сбросить поиск</Button>}
      </Card>

      <Card role="region" className="contact-result" tone={topic ? 'green' : 'gray'} aria-label="Рекомендация">
        <p role="status" className="contact-sr-only">{topic ? 'Рекомендация: ' + topic.title : searching
          ? matches.length > 1 ? 'Подходит несколько тем' : matchedPeople.length ? 'Найдены контакты' : 'Совпадений нет'
          : ''}</p>
        {topic ? <Recommendation topic={topic} query={query} contacts={contacts.data} canRequest={canRequest} prepare={prepare} />
          : searching && matches.length > 1 ? <>
            <h2 className="heading-m">Какая помощь нужна?</h2>
            <p className="body-secondary">Подходит несколько тем. Выбери одну, чтобы открыть нужный маршрут.</p>
            <div className="contact-actions">{matches.map((value) => (
              <Button key={value.id} size="s" variant="secondary" onClick={() => setChosen(value.id)}>{value.label}</Button>
            ))}</div>
          </> : searching ? <>
            <h2 className="heading-m">{matchedPeople.length ? 'Нашли контакты в справочнике' : 'Совпадений нет'}</h2>
            {matchedPeople.length ? <a className="contact-directory-link" href="#contact-directory">Показать контакты</a> : <>
              <p className="body-secondary">Попробуй другое слово или опиши ситуацию AI-buddy.</p>
              <Link className="btn btn--s btn--secondary" to="/chat">Спросить AI-buddy</Link>
            </>}
          </> : <>
            <span className="contact-result__icon" aria-hidden="true">↗</span>
            <h2 className="heading-m">Найди помощь по ситуации</h2>
            <p className="body-secondary">Выбери тему или введи вопрос, чтобы узнать, к кому обратиться и что сделать дальше.</p>
          </>}
      </Card>
    </div>

    {draft && <MessageDraft key={draft.version} draft={draft} close={() => {
      setDraft(undefined)
      trigger.current?.focus()
    }} />}
    <section className="contact-directory" id="contact-directory" aria-labelledby="contact-directory-heading">
      <h2 className="heading-m" id="contact-directory-heading">Справочник контактов</h2>
      {people.length ? <div className="contact-directory__grid">
        {people.map((person) => <ContactCard key={person.id} contact={person} prepare={prepare} />)}
      </div> : <p className="body-secondary">По текущему поиску контактов нет. Сбрось фильтр, чтобы увидеть весь справочник.</p>}
    </section>
  </div>
}
