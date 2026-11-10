import { useState } from 'react';
import type { ApiClient, Workspace } from '../api/types';

interface NextStepCardProps {
  workspace: Workspace;
  client: ApiClient;
}

export function NextStepCard({ workspace, client }: NextStepCardProps) {
  const [returnState, setReturnState] = useState<'idle' | 'sending' | 'recorded' | 'failed'>('idle');

  if (workspace.nextStep === null) return null;

  async function reportReturn() {
    if (returnState === 'sending') return;
    setReturnState('sending');
    try {
      await client.reportTaskReturn(
        workspace.task?.id ?? '',
        workspace.request?.id ?? null,
      );
      setReturnState('recorded');
    } catch {
      setReturnState('failed');
    }
  }

  const isReturnStep = workspace.nextStep.code === 'return-to-task';

  return (
    <section className="card" aria-labelledby="next-step-title">
      <div className="card-label">Следующий шаг</div>
      <h3 id="next-step-title">{workspace.nextStep.title}</h3>
      <ul>
        {workspace.nextStep.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>

      {isReturnStep && (
        <div className="return-block">
          {returnState !== 'recorded' && (
            <button
              className="btn btn-ok"
              onClick={() => void reportReturn()}
              disabled={returnState === 'sending'}
              data-testid="return-to-task"
            >
              {returnState === 'sending' ? 'Фиксируем…' : 'Вернуться к задаче'}
            </button>
          )}
          {returnState === 'recorded' && (
            <p className="notice notice-ok" role="status" data-testid="return-recorded">
              Зафиксировано: вы вернулись к задаче. Событие подтверждает намерение продолжить; права выдаёт сервер.
            </p>
          )}
          {returnState === 'failed' && (
            <div className="notice notice-err" role="alert">
              Не получилось зафиксировать событие. Проверьте соединение и повторите.
            </div>
          )}
        </div>
      )}
    </section>
  );
}

interface ProgressCardProps {
  workspace: Workspace;
  onRefresh: () => void;
  refreshing: boolean;
}

const decisionLabels: Record<string, string> = {
  pending: 'На согласовании',
  approved: 'Одобрена',
  rejected: 'Отклонена',
};

const accessTexts: Record<string, { label: string; hint: string }> = {
  granted: { label: 'Подтверждён сервером', hint: 'Ресурс доступен для работы' },
  denied: { label: 'Отсутствует', hint: 'Открыть ресурс сейчас нельзя' },
  unknown: { label: 'Неизвестно', hint: 'Сервер ещё не подтвердил право' },
};

export function ProgressCard({ workspace, onRefresh, refreshing }: ProgressCardProps) {
  const request = workspace.request;
  const access = accessTexts[workspace.effectiveAccess];

  if (request === null && workspace.effectiveAccess !== 'granted') return null;

  const approvedWithoutAccess =
    request !== null && request.status === 'approved' && workspace.effectiveAccess !== 'granted';

  return (
    <section className="card progress-card" aria-label="Карточка прогресса" data-testid="progress-card">
      <div className="card-label">Карточка прогресса</div>
      {request !== null && (
        <>
          <div className="progress-row">
            <span className="progress-key">Заявка</span>
            <span className="req-id" data-testid="progress-request-id">
              {request.id}
            </span>
            <span className={`badge badge-request-${request.status}`} data-testid="decision-badge">
              {decisionLabels[request.status]}
            </span>
          </div>
          <p className="muted small">Решение по заявке и доступность ресурса — независимые признаки.</p>
        </>
      )}
      <div className="progress-row">
        <span className="progress-key">Доступ к ресурсу</span>
        <span className={`badge badge-access-${workspace.effectiveAccess}`} data-testid="progress-access-badge">
          {access.label}
        </span>
      </div>
      <p className="muted small">{access.hint}</p>

      {approvedWithoutAccess && (
        <div className="notice notice-warn" role="status" data-testid="wait-access-note">
          Заявку одобрили, но право на ресурс сервером ещё не подтверждено ({access.label.toLowerCase()}). Начинать
          работу пока рано — обновите состояние чуть позже.
        </div>
      )}

      <button className="btn btn-ghost" onClick={onRefresh} disabled={refreshing}>
        {refreshing ? 'Проверяем…' : 'Обновить состояние'}
      </button>
    </section>
  );
}
