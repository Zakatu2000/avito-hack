import type { ChatAction, ChatReply } from '../api/schemas'

export interface ChatContext {
  userName: string
  mentorName: string
  nextStepTitle: string | null
}

export interface BotIntent {
  id: string
  keywords: string[]
  text: string
  actions?: ChatAction[]
}

export interface BotFallback {
  text: string
  actions?: ChatAction[]
}

export interface ChatEngine {
  readonly name: string
  reply(message: string, ctx: ChatContext): ChatReply
}

export function createKeywordEngine(intents: BotIntent[], fallback: BotFallback): ChatEngine {
  return {
    name: 'keyword',
    reply(message, ctx) {
      const normalized = message.toLowerCase().trim()
      let best: { intent: BotIntent; score: number } | null = null
      for (const intent of intents) {
        const score = intent.keywords.reduce(
          (acc, kw) => (normalized.includes(kw.toLowerCase()) ? acc + 1 : acc),
          0,
        )
        if (score > 0 && (!best || score > best.score)) best = { intent, score }
      }
      const source = best?.intent
      const text = renderTemplate(source?.text ?? fallback.text, ctx)
      return {
        intentId: source?.id ?? 'fallback',
        text,
        actions: source?.actions ?? fallback.actions ?? [],
      }
    },
  }
}

function renderTemplate(text: string, ctx: ChatContext): string {
  return text
    .replaceAll('{{userName}}', ctx.userName)
    .replaceAll('{{mentorName}}', ctx.mentorName)
    .replaceAll('{{nextStepTitle}}', ctx.nextStepTitle ?? 'первый пункт чек-листа')
}
