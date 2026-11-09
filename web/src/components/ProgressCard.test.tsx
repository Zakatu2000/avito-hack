import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../App';
import { TestApiClient } from '../api/testAdapter';
import { storeSession } from '../api/client';
import {
  exampleSessionTrainee,
  exampleWorkspaceApprovedNoAccess,
      exampleWorkspaceGranted,
  exampleWorkspacePending,
      exampleWorkspaceRejected,
} from '../api/fixtures';
import { ProgressCard } from './ProgressCard';

describe('ProgressCard: раздельные признаки', () => {
  it('pending: ID заявки, решение и доступ показаны раздельно', () => {
    render(
      <ProgressCard workspace={exampleWorkspacePending} onRefresh={() => undefined} refreshing={false} />,
    );
    expect(screen.getByTestId('progress-request-id')).toHaveTextContent('REQ-2026-0142');
    expect(screen.getByTestId('decision-badge')).toHaveTextContent('На согласовании');
    expect(screen.getByTestId('progress-access-badge')).toHaveTextContent('Отсутствует');
    expect(screen.queryByTestId('wait-access-note')).not.toBeInTheDocument();
  });

  it('одобрено без права: есть объяснение ожидания, нет предложения начать работу', () => {
    render(
      <ProgressCard
        workspace={exampleWorkspaceApprovedNoAccess}
        onRefresh={() => undefined}
        refreshing={false}
      />,
    );
    expect(screen.getByTestId('decision-badge')).toHaveTextContent('Одобрена');
    expect(screen.getByTestId('progress-access-badge')).toHaveTextContent('Неизвестно');
    expect(screen.getByTestId('wait-access-note')).toHaveTextContent('Начинать работу пока рано');
  });

  it('после выдачи права показан следующий шаг из задачи', () => {
    render(
      <ProgressCard workspace={exampleWorkspaceGranted} onRefresh={() => undefined} refreshing={false} />,
    );
    expect(screen.getByTestId('progress-access-badge')).toHaveTextContent('Подтверждён сервером');
    expect(screen.queryByTestId('wait-access-note')).not.toBeInTheDocument();
  });

  it('отказ: статус отклонена, без закрытых сведений', () => {
    render(
      <ProgressCard workspace={exampleWorkspaceRejected} onRefresh={() => undefined} refreshing={false} />,
    );
    expect(screen.getByTestId('decision-badge')).toHaveTextContent('Отклонена');
  });
});

describe('F4: восстановление и следующий шаг', () => {
  it('после «перезагрузки» (новый клиент и монтирование) сохраняется тот же ID заявки', async () => {
    const client = new TestApiClient();
    storeSession(exampleSessionTrainee);
    client.setDemoPhase('pending');

    const first = render(<App client={client} />);
    expect(await screen.findByTestId('progress-request-id')).toHaveTextContent('REQ-2026-0142');
    first.unmount();

    const reloadedClient = new TestApiClient();
    render(<App client={reloadedClient} />);
    expect(await screen.findByTestId('progress-request-id')).toHaveTextContent('REQ-2026-0142');
    expect(screen.getByTestId('decision-badge')).toHaveTextContent('На согласовании');
  });

  it('переход approved → granted по кнопке обновления: появляется шаг из задачи и кнопка возврата', async () => {
    const client = new TestApiClient();
    storeSession(exampleSessionTrainee);
    client.setDemoPhase('approved');

    render(<App client={client} />);
    expect(await screen.findByTestId('wait-access-note')).toBeInTheDocument();
    expect(screen.queryByTestId('return-to-task')).not.toBeInTheDocument();

    client.setDemoPhase('granted');
    await userEvent.click(screen.getAllByRole('button', { name: 'Обновить состояние' })[0]);

    expect(await screen.findByTestId('return-to-task')).toBeInTheDocument();
    expect(screen.getByText('Следующий шаг по задаче')).toBeInTheDocument();
    expect(screen.getByText(/Склонируйте репозиторий todo-service/)).toBeInTheDocument();
  });

  it('кнопка «Вернуться к задаче» отправляет событие с ID заявки и фиксирует его', async () => {
    const client = new TestApiClient();
    storeSession(exampleSessionTrainee);
    client.setDemoPhase('granted');

    render(<App client={client} />);
    await screen.findByTestId('return-to-task');
    await userEvent.click(screen.getByTestId('return-to-task'));

    expect(await screen.findByTestId('return-recorded')).toBeInTheDocument();
    expect(client.recordedEvents()).toEqual([
      { name: 'task_returned', taskId: 'TSK-101', requestId: 'REQ-2026-0142' },
    ]);
  });

  it('в состоянии approved без права кнопки возврата к задаче нет даже после повторного вопроса', async () => {
    const client = new TestApiClient();
    storeSession(exampleSessionTrainee);
    client.setDemoPhase('approved');

    render(<App client={client} />);
    await screen.findByTestId('wait-access-note');

    await userEvent.type(screen.getByLabelText('Текст вопроса'), 'Могу начинать?');
    await userEvent.click(screen.getByRole('button', { name: 'Спросить' }));

    expect(await screen.findByText(/REQ-2026-0142 — одобрена/)).toBeInTheDocument();
    expect(screen.queryByTestId('return-to-task')).not.toBeInTheDocument();
  });
});
