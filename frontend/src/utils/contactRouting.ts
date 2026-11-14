import type { Contact, ContactRole } from '../api/schemas'

export type HelpAction = { label: string; to: string; request?: 'existing' | 'server' }

export interface HelpTopic {
  id: string
  label: string
  icon: string
  title: string
  description: string
  roles: ContactRole[]
  keywords: string[]
  message: string
  actions: HelpAction[]
}

export const HELP_TOPICS: HelpTopic[] = [
  {
    id: 'access', label: 'Доступы', icon: '🔑', title: 'Запросить доступ',
    description: 'Выберите систему и объясните, зачем она нужна. Заявка попадёт на согласование в вашу команду.',
    roles: ['lead'], keywords: ['доступ', 'прав', 'репозитори', 'jira', 'confluence', 'grafana', 'access'],
    message: 'Нужен доступ к системе или репозиторию.',
    actions: [{ label: 'Открыть форму доступа', to: '/requests/new/access', request: 'existing' }],
  },
  {
    id: 'support', label: 'Техническая проблема', icon: '🛠️', title: 'Техническая помощь',
    description: 'Опишите ошибку и шаги, на которых она возникает. Команда сможет взять обращение в работу.',
    roles: [], keywords: ['впн', 'vpn', 'сет', 'окружен', 'ошиб', 'запуска', 'запуск', 'лома', 'слом', 'git', 'сборк', 'техподдерж', 'техническ'],
    message: 'Столкнулся с технической проблемой.',
    actions: [{ label: 'Создать обращение', to: '/requests/new/technical_support', request: 'server' }],
  },
  {
    id: 'first-task', label: 'Первая задача', icon: '🧭', title: 'Обсудить задачу с наставником',
    description: 'Запросите консультацию, чтобы разобрать первую задачу, ожидания или замечания к коду.',
    roles: ['mentor'], keywords: ['задач', 'настав', 'ревью', 'review', 'адаптац', 'консультац'],
    message: 'Хочу обсудить задачу и уточнить, с чего лучше начать.',
    actions: [{ label: 'Запросить консультацию', to: '/requests/new/mentor_consultation', request: 'server' }],
  },
  {
    id: 'leave', label: 'Отгул', icon: '📅', title: 'Оформить отгул',
    description: 'Укажите даты и причину. В разделе «Запросы» можно будет посмотреть статус согласования.',
    roles: ['lead'], keywords: ['отгул', 'отпуск', 'выходн', 'отсутств', 'больнич'],
    message: 'Хочу уточнить, как согласовать отгул.',
    actions: [{ label: 'Открыть форму отгула', to: '/requests/new/leave', request: 'existing' }],
  },
  {
    id: 'learning', label: 'Обучение', icon: '📚', title: 'Найти учебный материал',
    description: 'Начните с базы знаний. Если подходящего материала нет, отправьте наставнику запрос на рекомендацию.',
    roles: ['mentor'], keywords: ['обуч', 'изуч', 'курс', 'материал', 'учебн', 'микросервис', 'лекци'],
    message: 'Ищу учебные материалы по теме.',
    actions: [
      { label: 'Открыть базу знаний', to: '/kb' },
      { label: 'Запросить материал', to: '/requests/new/learning_request', request: 'server' },
    ],
  },
  {
    id: 'people', label: 'Вопрос к HR или куратору', icon: '🤝', title: 'Выбрать HR или куратора',
    description: 'К HR обычно обращаются по документам и выплатам, к куратору — по мероприятиям и сообществу стажёров.',
    roles: ['hr', 'curator'], keywords: ['hr', 'эйчар', 'куратор', 'документ', 'выплат', 'мероприяти', 'экватор', 'сообществ', 'стажировк'],
    message: 'Хочу уточнить организационный вопрос по стажировке.',
    actions: [],
  },
]

function words(value: string) {
  return value.toLocaleLowerCase('ru').replaceAll('ё', 'е').match(/[\p{L}\p{N}]+/gu) ?? []
}

export function matchHelpTopics(value: string) {
  const tokens = words(value)
  return HELP_TOPICS.filter((topic) => topic.keywords.some((keyword) => tokens.some((token) => token.startsWith(keyword))))
}

export function matchContacts(contacts: Contact[], value: string) {
  const query = words(value)
  return contacts.filter((contact) => {
    const text = words([contact.name, contact.role, ...contact.helpsWith].join(' '))
    return query.length > 0 && query.every((term) => text.some((token) => token.startsWith(term)))
  })
}

export function actionsForTopic(topic: HelpTopic, query: string): HelpAction[] {
  const tokens = words(query)
  const has = (...prefixes: string[]) => tokens.some((token) => prefixes.some((prefix) => token.startsWith(prefix)))
  return topic.actions.map((action) => {
    const params = new URLSearchParams()
    if (topic.id === 'access') {
      const systems = [
        ['repo', ['репозитори']], ['jira', ['jira']], ['confluence', ['confluence']], ['grafana', ['grafana']],
      ] as const
      const found = systems.filter(([, aliases]) => has(...aliases))
      if (found.length === 1) params.set('system', found[0][0])
    } else if (topic.id === 'support') {
      if (has('vpn', 'впн', 'сет')) params.set('category', 'network')
      else if (has('git', 'репозитори')) params.set('category', 'git')
      else if (has('окружен', 'сборк', 'запуск')) params.set('category', 'environment')
    } else if (topic.id === 'first-task') {
      params.set('topic', 'Первая задача и адаптация')
    }
    return params.size ? { ...action, to: action.to + '?' + params } : action
  })
}

export function messageTemplate(subject: string) {
  return `Здравствуйте! ${subject}\n\nЧто случилось:\n\nЧто уже попробовал(а):\n\nКакая помощь нужна:\n`
}
