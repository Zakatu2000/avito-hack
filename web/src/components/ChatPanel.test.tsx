import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatPanel } from './ChatPanel';
import { ApiError, NetworkError } from '../api/errors';
import type { ApiClient, ConfirmResult, MessageReply } from '../api/types';
import { exampleProposal, exampleRequestPending } from '../api/fixtures';

function reply(overrides: Partial<MessageReply>): MessageReply {
  return {
    type: 'text',
    text: 'Ответ',
    source: 'workspace',
    proposal: null,
    request: null,
    nextStep: null,
    aiMode: 'demo',
    ...overrides,
  };
}

function stubClient(overrides: Partial<ApiClient>): ApiClient {
  return {
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
    getWorkspace: vi.fn().mockResolvedValue(undefined),
    sendMessage: vi.fn(),
    confirmProposal: vi.fn(),
    reportTaskReturn: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as ApiClient;
}

function renderPanel(client: ApiClient) {
  const onRefresh = vi.fn().mockResolvedValue(undefined);
  render(<ChatPanel client={client} onRefresh={onRefresh} instruction={{ title: 'Инструкция «Первый PR»', url: 'https://intranet.example/i' }} />);
  return { onRefresh };
}

async function ask(text: string) {
  await userEvent.type(screen.getByLabelText('Текст вопроса'), text);
  await userEvent.click(screen.getByRole('button', { name: 'Спросить' }));
}

describe('ChatPanel: диалог', () => {
  it('показывает приветствие до первого вопроса', () => {
    const client = stubClient({});
    renderPanel(client);
    expect(screen.getByText(/Опишите проблему своими словами/)).toBeInTheDocument();
  });

  it('уточнение приходит с источником, экран показывает ожидание', async () => {
    let resolveSend: (value: MessageReply) => void = () => undefined;
    const client = stubClient({
      sendMessage: vi.fn(
        () =>
          new Promise<MessageReply>((resolve) => {
            resolveSend = resolve;
          }),
      ),
    });
    renderPanel(client);

    await ask('Не могу начать первую задачу. Что делать?');
    expect(screen.getByText('Не могу начать первую задачу. Что делать?')).toBeInTheDocument();
    expect(screen.getByTestId('assistant-thinking')).toHaveTextContent('Помощник проверяет…');
    expect(screen.getByRole('button', { name: 'Отправляем…' })).toBeDisabled();

    resolveSend(reply({ type: 'clarification', text: 'Речь о репозитории задачи #TSK-101?' }));
    await waitFor(() => expect(screen.getByText('Речь о репозитории задачи #TSK-101?')).toBeInTheDocument());
    expect(screen.getByText('Источник: workspace')).toBeInTheDocument();
    expect(screen.queryByTestId('assistant-thinking')).not.toBeInTheDocument();
  });

  it('сетевой сбой при отправке: сначала восстановление серверного состояния, ошибка не выглядит успехом', async () => {
    const client = stubClient({ sendMessage: vi.fn().mockRejectedValue(new NetworkError()) });
    const { onRefresh } = renderPanel(client);

    await ask('Не могу начать первую задачу. Что делать?');

    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1));
    expect(screen.getByText('Не получилось связаться с сервером. Показываю состояние из последнего ответа.')).toBeInTheDocument();
    expect(screen.getByText('ошибка связи')).toBeInTheDocument();
    expect(screen.queryByText(/Заявка создана/)).not.toBeInTheDocument();
  });
});

describe('ChatPanel: предложение и подтверждение', () => {
  function proposalReply(): MessageReply {
    return reply({
      type: 'proposal',
      text: 'Могу создать заявку на доступ.',
      source: 'проверка назначения и права сервером',
      proposal: { ...exampleProposal },
    });
  }

  it('карточка показывает ресурс, цель и действие; подтверждение выводит номер и статус', async () => {
    const client = stubClient({
      sendMessage: vi.fn().mockResolvedValueOnce(proposalReply()),
      confirmProposal: vi.fn().mockResolvedValue({ request: exampleRequestPending, nextStep: null }),
    });
    const { onRefresh } = renderPanel(client);

    await ask('Про репозиторий, он не открывается');
    const card = screen.getByTestId(`proposal-${exampleProposal.id}`);
    expect(card).toHaveTextContent('git.avito.local/trainee/todo-service');
    expect(card).toHaveTextContent('доступ для выполнения задачи #TSK-101');
    expect(card).toHaveTextContent('Создать заявку на доступ (роль: reporter)');
    expect(screen.getByRole('link', { name: 'Инструкция «Первый PR»' })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Подтвердить' }));

    expect(await screen.findByTestId(`proposal-${exampleProposal.id}-result`)).toHaveTextContent('REQ-2026-0142');
    expect(screen.getByText(/Заявка создана: REQ-2026-0142 — на согласовании/)).toBeInTheDocument();
    expect(client.confirmProposal).toHaveBeenCalledWith('PRP-77', 'idem-REQ-2026-0142');
    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1));
  });

  it('повторный клик не создаёт вторую заявку: кнопка блокируется, подтверждение вызывается один раз', async () => {
    const client = stubClient({
      sendMessage: vi.fn().mockResolvedValueOnce(proposalReply()),
      confirmProposal: vi.fn(
        () =>
          new Promise<ConfirmResult>((resolve) => {
            setTimeout(() => resolve({ request: exampleRequestPending, nextStep: null }), 40);
          }),
      ),
    });
    renderPanel(client);

    await ask('Про репозиторий, он не открывается');
    const confirmButton = screen.getByRole('button', { name: 'Подтвердить' });
    await userEvent.click(confirmButton);

    expect(screen.getByRole('button', { name: 'Создаём заявку…' })).toBeDisabled();

    await waitFor(() => expect(screen.getByTestId(`proposal-${exampleProposal.id}-result`)).toBeInTheDocument());
    expect(client.confirmProposal).toHaveBeenCalledTimes(1);
    expect(screen.getAllByText('REQ-2026-0142').length).toBeGreaterThan(0);
  });

  it('ошибка подтверждения показывается как ошибка, а не как успех', async () => {
    const client = stubClient({
      sendMessage: vi.fn().mockResolvedValueOnce(proposalReply()),
      confirmProposal: vi.fn().mockRejectedValue(new ApiError(409, 'Предложение устарело')),
    });
    const { onRefresh } = renderPanel(client);

    await ask('Про репозиторий, он не открывается');
    await userEvent.click(screen.getByRole('button', { name: 'Подтвердить' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Предложение устарело');
    expect(screen.queryByText(/Заявка создана/)).not.toBeInTheDocument();
    expect(onRefresh).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Подтвердить' })).toBeInTheDocument();
  });

  it('отмена до отправки: ничего не отправляется на сервер', async () => {
    const client = stubClient({ sendMessage: vi.fn().mockResolvedValueOnce(proposalReply()) });
    const { onRefresh } = renderPanel(client);

    await ask('Про репозиторий, он не открывается');
    await userEvent.click(screen.getByRole('button', { name: 'Не сейчас' }));

    expect(await screen.findByTestId(`proposal-${exampleProposal.id}-declined`)).toBeInTheDocument();
    expect(client.confirmProposal).not.toHaveBeenCalled();
    expect(onRefresh).not.toHaveBeenCalled();
    expect(screen.getByText('Отменено вами — заявка не создана.')).toBeInTheDocument();
  });

  it('при существующей заявке агент показывает её статус без нового предложения', async () => {
    const client = stubClient({
      sendMessage: vi.fn().mockResolvedValueOnce(
        reply({
          type: 'request-status',
          text: 'Заявка REQ-2026-0142 — на согласовании. Новая заявка не нужна.',
          source: 'workspace.request',
          request: exampleRequestPending,
        }),
      ),
    });
    const { onRefresh } = renderPanel(client);

    await ask('Что-то всё равно не открывается, я уже спрашивал');

    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1));
    expect(screen.getByText(/REQ-2026-0142 — на согласовании/)).toBeInTheDocument();
    expect(screen.queryByTestId(`proposal-${exampleProposal.id}`)).not.toBeInTheDocument();
  });
});
