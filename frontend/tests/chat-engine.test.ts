import { describe, expect, it } from 'vitest'
import { createKeywordEngine, type BotFallback, type BotIntent } from '../src/chat/engine'

const INTENTS: BotIntent[] = [
  {
    id: 'leave',
    keywords: ['отгул', 'отпуск'],
    text: 'Отгул оформляется тут. Наставница {{mentorName}} согласует.',
    actions: [{ id: 'a1', label: 'Оформить отгул', kind: 'navigate', target: '/requests/new/leave' }],
  },
  {
    id: 'access',
    keywords: ['доступ', 'jira'],
    text: 'Доступ запроси у руководителя.',
    actions: [],
  },
  {
    id: 'multi',
    keywords: ['доступ', 'срочно'],
    text: 'Срочный доступ — экстренная ветка.',
  },
]

const FALLBACK: BotFallback = {
  text: '{{userName}}, не понял вопрос. Напиши {{mentorName}}.',
  actions: [{ id: 'c', label: 'Написать наставнице', kind: 'contact', target: 'c-mentor' }],
}

const CTX = { userName: 'Аня', mentorName: 'Марина', nextStepTitle: 'Чаты и каналы' }

const engine = createKeywordEngine(INTENTS, FALLBACK)

describe('ChatEngine (spec: frontend/specs/005-chat-bot.md)', () => {
  it('матчит интент по ключевому слову без учёта регистра', () => {
    const reply = engine.reply('Как оформить ОТПУСК?', CTX)
    expect(reply.intentId).toBe('leave')
    expect(reply.text).toContain('Марина')
    expect(reply.actions[0]?.target).toBe('/requests/new/leave')
  })

  it('выбирает интент с максимальным числом совпадений', () => {
    const reply = engine.reply('нужен доступ срочно', CTX)
    expect(reply.intentId).toBe('multi')
  })

  it('подставляет имя пользователя и следующий шаг в шаблон', () => {
    const fallback = engine.reply('абракадабра', CTX)
    expect(fallback.intentId).toBe('fallback')
    expect(fallback.text).toContain('Аня')
    expect(fallback.text).toContain('Марина')
    expect(fallback.actions[0]?.kind).toBe('contact')
  })

  it('возвращает пустые действия, если у интента их нет', () => {
    const reply = engine.reply('доступ', CTX)
    expect(reply.actions).toEqual([])
  })

  it('использует подстановку следующего шага, если он есть', () => {
    const withNext = createKeywordEngine(
      [{ id: 'plan', keywords: ['план'], text: 'Дальше: {{nextStepTitle}}' }],
      FALLBACK,
    )
    expect(withNext.reply('что по плану', CTX).text).toBe('Дальше: Чаты и каналы')
    const noNext = withNext.reply('что по плану', { ...CTX, nextStepTitle: null })
    expect(noNext.text).toBe('Дальше: первый пункт чек-листа')
  })
})
