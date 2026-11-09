import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from './App';
import { storeSession } from './api/client';
import { ApiError, SessionExpiredError } from './api/errors';
import { TestApiClient } from './api/testAdapter';
import type { ApiClient, Workspace } from './api/types';
import { exampleSessionTrainee, exampleWorkspaceInitial } from './api/fixtures';

function stubClient(overrides: Partial<ApiClient>): ApiClient {
  return {
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
    getWorkspace: vi.fn(),
    sendMessage: vi.fn(),
    confirmProposal: vi.fn(),
    ...overrides,
  } as ApiClient;
}

describe('App: вход и первый экран', () => {
  it('без сессии показывает тестовый вход, вход ведёт к рабочему экрану', async () => {
    const client = new TestApiClient();
    render(<App client={client} />);

    expect(screen.getByRole('button', { name: /Войти как Вася Стажёр/ })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Войти как Вася Стажёр/ }));

    expect(await screen.findByText(/Настроить CI для учебного сервиса/)).toBeInTheDocument();
    expect(screen.getByTestId('access-badge')).toHaveTextContent('Ресурс недоступен');
    expect(screen.getByText(/Инструкция «Первый PR»/)).toBeInTheDocument();
    expect(screen.getByTestId('aimode-badge')).toHaveTextContent('демо');
    expect(screen.getByRole('button', { name: 'Обновить состояние' })).toBeInTheDocument();
  });

  it('до ответа сервера показывает состояние загрузки', () => {
    const client = stubClient({
      getWorkspace: vi.fn(() => new Promise<Workspace>(() => undefined)),
    });
    storeSession(exampleSessionTrainee);
    render(<App client={client} />);

    expect(screen.getByTestId('loading-state')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Загружаем рабочее пространство');
  });

  it('при ошибке показывает экран ошибки, «Повторить» восстанавливает данные', async () => {
    const getWorkspace = vi
      .fn<() => Promise<Workspace>>()
      .mockRejectedValueOnce(new ApiError(500, 'Ошибка сервера (500)'))
      .mockResolvedValueOnce(exampleWorkspaceInitial);
    const client = stubClient({ getWorkspace });
    storeSession(exampleSessionTrainee);
    render(<App client={client} />);

    expect(await screen.findByTestId('error-state')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Ошибка сервера (500)');

    await userEvent.click(screen.getByRole('button', { name: 'Повторить' }));

    expect(await screen.findByText(/Настроить CI для учебного сервиса/)).toBeInTheDocument();
    expect(getWorkspace).toHaveBeenCalledTimes(2);
  });

  it('истечение сессии возвращает на экран входа с пояснением', async () => {
    const client = stubClient({
      getWorkspace: vi.fn().mockRejectedValue(new SessionExpiredError()),
    });
    storeSession(exampleSessionTrainee);
    render(<App client={client} />);

    expect(await screen.findByTestId('expired-note')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Войти как Вася Стажёр/ })).toBeInTheDocument();
  });

  it('демооператор видит пустой экран без чужих заявок', async () => {
    const client = new TestApiClient();
    render(<App client={client} />);

    await userEvent.click(screen.getByRole('button', { name: /Войти как Демооператор/ }));

    expect(await screen.findByText('Задача пока не назначена.')).toBeInTheDocument();
    expect(screen.queryByTestId('request-badge')).not.toBeInTheDocument();
  });
});
