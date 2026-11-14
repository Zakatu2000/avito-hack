import { describe, expect, it } from 'vitest'
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AccessFormPage } from '../src/pages/AccessFormPage'
import { ChatPage } from '../src/pages/ChatPage'
import { HomePage } from '../src/pages/HomePage'
import { KbPage } from '../src/pages/KbPage'
import { LeaveFormPage } from '../src/pages/LeaveFormPage'
import { MetricsPage } from '../src/pages/MetricsPage'
import { RequestsPage } from '../src/pages/RequestsPage'
import { TeamPage } from '../src/pages/TeamPage'
import { TimelinePage } from '../src/pages/TimelinePage'
import { useDevStore } from '../src/stores/dev'
import { useChatStore } from '../src/stores/chat'
import { loginAs, renderApp, renderWithProviders } from './helpers'

describe('Вход тестовым пользователем (spec: frontend/specs/004-roles-permissions.md)', () => {
  it('перенаправляет на /login без входа и пускает дальше после выбора', async () => {
    window.history.replaceState({}, '', '/')
    renderApp()
    expect(await screen.findByText('Войти как тестовый пользователь')).toBeInTheDocument()

    await userEvent.click(await screen.findByText('Аня Петрова'))
    expect(await screen.findByText(/Привет, Аня/i)).toBeInTheDocument()
    expect(window.location.pathname).toBe('/')
  })

  it('показывает роли пользователей', async () => {
    renderApp()
    expect(await screen.findByText('Марина Ким')).toBeInTheDocument()
    expect(screen.getByText('наставник')).toBeInTheDocument()
    expect(screen.getByText('руководитель')).toBeInTheDocument()
  })
})

describe('Главная (spec: frontend/specs/001-adaptation-track.md)', () => {
  it('показывает прогресс, следующий шаг и быстрые действия', async () => {
    loginAs('intern')
    renderWithProviders(<HomePage />)
    expect(await screen.findByText('Прогресс адаптации')).toBeInTheDocument()
    expect(screen.getByText(/2 из 17 пунктов/)).toBeInTheDocument()
    expect(screen.getAllByText('Доступы: Confluence и Jira').length).toBeGreaterThan(0)
    expect(screen.getByText('Оформить отгул')).toBeInTheDocument()
    expect(screen.getByText('Запросить доступ')).toBeInTheDocument()
  })

  it('наставнику показывает очередь согласования вместо следующего шага', async () => {
    loginAs('mentor')
    renderWithProviders(<HomePage />)
    expect(await screen.findByText('Очередь согласования')).toBeInTheDocument()
    expect(screen.getByText(/Ждут твоего решения/i)).toBeInTheDocument()
  })
})

describe('Таймлайн адаптации (spec: frontend/specs/001-adaptation-track.md)', () => {
  it('стажёр ведёт пункт от «не начато» до готово без согласования', async () => {
    loginAs('intern')
    renderWithProviders(<TimelinePage />)
    const env = await screen.findByText('Документы и мануалы')
    expect(env).toBeInTheDocument()

    const startButton = within(env.closest('.list-item') as HTMLElement).getByRole('button', { name: 'Начать' })
    await userEvent.click(startButton)
    expect(
      await within(env.closest('.list-item') as HTMLElement).findByRole('button', { name: 'Готово' }),
    ).toBeInTheDocument()

    await userEvent.click(within(env.closest('.list-item') as HTMLElement).getByRole('button', { name: 'Готово' }))
    await waitFor(() =>
      expect(within(env.closest('.list-item') as HTMLElement).queryByRole('button')).not.toBeInTheDocument(),
    )
  })

  it('стажёр отправляет пункт на согласование и не может сам подтвердить', async () => {
    loginAs('intern')
    renderWithProviders(<TimelinePage />)
    const okr = await screen.findByText('Цели и OKR')
    const item = okr.closest('.list-item') as HTMLElement
    await userEvent.click(within(item).getByRole('button', { name: 'Начать' }))
    expect(await within(item).findByRole('button', { name: 'На проверку' })).toBeInTheDocument()
    await userEvent.click(within(item).getByRole('button', { name: 'На проверку' }))
    await waitFor(() => {
      expect(within(item).getAllByText('Ждёт согласования').length).toBeGreaterThan(0)
    })
    expect(within(item).queryByRole('button')).not.toBeInTheDocument()
  })

  it('наставник подтверждает пункты стажёров в разделе «Команда»', async () => {
    loginAs('mentor')
    renderWithProviders(<TeamPage />)
    const section = await screen.findByRole('region', { name: 'Пункты на подтверждение' })
    const pendingRow = within(section).getByText(/1:1 с наставником/)
    await userEvent.click(within(pendingRow.closest('.list-item') as HTMLElement).getByRole('button', { name: 'Подтвердить' }))
    await waitFor(() => {
      expect(within(section).queryByText(/1:1 с наставником/)).not.toBeInTheDocument()
    })
  })
})

describe('Отгул: форма → превью → отправка → статус (spec: frontend/specs/003-leave-request.md)', () => {
  it('проходит полный сценарий и сохраняется в «Мои запросы»', async () => {
    loginAs('intern')
    const { unmount } = renderWithProviders(<LeaveFormPage />)

    fireEvent.change(await screen.findByLabelText('Дата начала'), { target: { value: '2026-11-20' } })
    fireEvent.change(screen.getByLabelText('Дата окончания'), { target: { value: '2026-11-21' } })
    await userEvent.selectOptions(screen.getByLabelText('Причина'), 'personal')

    await userEvent.click(screen.getByRole('button', { name: 'Предпросмотр и отправка' }))
    const dialog = await screen.findByRole('dialog', { name: 'Проверь запрос' })
    expect(within(dialog).getByText(/20\.11\.2026 — 21\.11\.2026/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Марина Ким/)).toBeInTheDocument()

    await userEvent.click(within(dialog).getAllByRole('button', { name: 'Отправить' })[0]!)
    expect(await screen.findByText('Запрос отправлен наставнику и руководителю')).toBeInTheDocument()
    unmount()

    renderWithProviders(<RequestsPage />)
    const summary = await screen.findByText('Отгул: 20.11.2026 — 21.11.2026')
    expect(summary).toBeInTheDocument()
    expect(summary.closest('details')!).toHaveTextContent('Отправлен')
    expect(summary.closest('details')!).toHaveTextContent('Согласуют')
  })

  it('валидирует даты до открытия превью', async () => {
    loginAs('intern')
    renderWithProviders(<LeaveFormPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Предпросмотр и отправка' }))
    expect((await screen.findAllByText('Формат даты ГГГГ-ММ-ДД')).length).toBeGreaterThan(0)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('Доступ: черновик → отправка → цепочка статусов (spec: frontend/specs/002-access-request.md)', () => {
  it('сохраняет черновик и отправляет его из списка', async () => {
    loginAs('intern')
    const { unmount } = renderWithProviders(<AccessFormPage />)
    await userEvent.selectOptions(await screen.findByLabelText('Система'), 'confluence')
    await userEvent.type(
      screen.getByLabelText('Для какой задачи нужен доступ'),
      'Читаю документацию команды по ревью',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Предпросмотр и отправка' }))
    const dialog = await screen.findByRole('dialog', { name: 'Проверь запрос' })
    expect(within(dialog).getByText(/Confluence/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Олег Ветров/)).toBeInTheDocument()

    await userEvent.click(within(dialog).getByRole('button', { name: 'Сохранить черновик' }))
    expect(await screen.findByText('Черновик сохранён')).toBeInTheDocument()
    unmount()

    renderWithProviders(<RequestsPage />)
    const accessCard = (await screen.findByText('Доступ: confluence')).closest('details') as HTMLElement
    expect(within(accessCard).getByText('Черновик')).toBeInTheDocument()
    await userEvent.click(within(accessCard).getByRole('button', { name: 'Отправить' }))
    expect((await within(accessCard).findAllByText('Отправлен')).length).toBeGreaterThan(0)
  })

  it('наставник закрывает запрос из очереди', async () => {
    loginAs('mentor')
    renderWithProviders(<RequestsPage />)
    const queue = await screen.findByRole('region', { name: 'Очередь согласования' })
    const jiraRow = within(queue).getByText(/Марк Соколов: Доступ: jira/).closest('.list-item') as HTMLElement
    await userEvent.click(within(jiraRow).getByRole('button', { name: 'Вынести решение' }))
    expect((await screen.findAllByText('На согласовании')).length).toBeGreaterThan(0)
    await userEvent.click(screen.getAllByRole('button', { name: 'Вынести решение' })[0]!)
    expect((await screen.findAllByText('Выдан')).length).toBeGreaterThan(0)
  })
})

describe('Чат с ботом (spec: frontend/specs/005-chat-bot.md)', () => {
  it('приветствует, отвечает по интенту и даёт карточку действия', async () => {
    loginAs('intern')
    renderWithProviders(<ChatPage />)
    expect(await screen.findByText(/Спроси коротко/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Как оформить отгул?' }))
    const reply = await screen.findByText(/согласовать/i)
    expect(reply).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Оформить отгул' })).toBeInTheDocument()
  })

  it('честно отвечает «не понял» и предлагает наставника', async () => {
    loginAs('intern')
    renderWithProviders(<ChatPage />)
    const input = await screen.findByLabelText('Сообщение боту')
    await userEvent.type(input, 'квантовая механика{Enter}')
    expect(await screen.findByText(/не понял/i)).toBeInTheDocument()
    expect(await screen.findByText(/Марина Ким/)).toBeInTheDocument()
  })

  it('создаёт, переключает и удаляет серверные чаты с их историей', async () => {
    loginAs('intern')
    const { unmount } = renderWithProviders(<ChatPage />)
    await screen.findByText(/Спроси коротко/i)

    await userEvent.click(screen.getByRole('button', { name: 'Как оформить отгул?' }))
    expect(await screen.findByText(/согласовать/i)).toBeInTheDocument()

    const chatList = screen.getByLabelText('Список чатов')
    await userEvent.click(screen.getByRole('button', { name: '+ Новый чат' }))
    await screen.findByRole('button', { name: /^Новый чат$/ })
    await userEvent.click(within(chatList).getByRole('button', { name: 'Как оформить отгул?' }))
    expect(await screen.findByText(/согласовать/i)).toBeInTheDocument()

    // Simulate a reload: clear the in-memory transcript but keep the selected
    // chat id; the new page must restore messages from the API history endpoint.
    unmount()
    useChatStore.setState({ messages: [], typing: false, lastUserMessage: null })
    renderWithProviders(<ChatPage />)
    expect(await screen.findByText(/согласовать/i)).toBeInTheDocument()
    const reloadedChatList = screen.getByLabelText('Список чатов')

    await userEvent.click(within(reloadedChatList).getByRole('button', { name: 'Удалить чат «Как оформить отгул?»' }))
    await waitFor(() => {
      expect(within(reloadedChatList).queryByRole('button', { name: 'Как оформить отгул?' })).not.toBeInTheDocument()
    })
  })

  it('при сбое сервиса показывает ошибку и повтор работает', async () => {
    loginAs('intern')
    useDevStore.setState({ failureMode: 'always' })
    renderWithProviders(<ChatPage />)
    await screen.findByText(/Спроси коротко/i)
    await userEvent.click(screen.getByRole('button', { name: 'Что дальше по плану?' }))
    expect(await screen.findByText('Не доставлено')).toBeInTheDocument()

    useDevStore.setState({ failureMode: 'off' })
    await userEvent.click(screen.getByRole('button', { name: 'Повторить' }))
    expect(await screen.findByText(/следующий шаг/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Открыть таймлайн' })).toBeInTheDocument()
  })
})

describe('Вид команды и права (spec: frontend/specs/004-roles-permissions.md)', () => {
  it('стажёру API отдаёт 403 и интерфейс показывает «нет доступа»', async () => {
    loginAs('intern')
    renderWithProviders(<TeamPage />)
    expect(await screen.findByText('Нет доступа')).toBeInTheDocument()
    expect(screen.getByText(/доступна только наставникам/i)).toBeInTheDocument()
  })

  it('наставник видит стажёров с прогрессом и очередь', async () => {
    loginAs('mentor')
    renderWithProviders(<TeamPage />)
    expect(await screen.findByText('Аня Петрова')).toBeInTheDocument()
    expect(screen.getByText('Марк Соколов')).toBeInTheDocument()
    expect(await screen.findByRole('region', { name: 'Очередь согласования' })).toBeInTheDocument()
  })
})

describe('База знаний и метрики', () => {
  it('помечает все статьи как тестовые данные', async () => {
    loginAs('intern')
    renderWithProviders(<KbPage />)
    expect(await screen.findByText('База знаний')).toBeInTheDocument()
    expect(screen.getAllByText(/Тестовые данные, не регламент Авито/i).length).toBeGreaterThan(1)
  })

  it('показывает макет метрик на моковых данных', async () => {
    loginAs('intern')
    renderWithProviders(<MetricsPage />)
    expect(await screen.findByText('52 ч')).toBeInTheDocument()
    expect(screen.getByText('62%')).toBeInTheDocument()
    expect(screen.getByText('3.2 дн')).toBeInTheDocument()
    expect(screen.getByText(/не реальные метрики/i)).toBeInTheDocument()
  })
})
