import type { ApiClient, Workspace } from '../api/types';
import { ChatPanel } from './ChatPanel';
import { NextStepCard, ProgressCard } from './ProgressCard';

interface WorkspaceBodyProps {
  workspace: Workspace;
  client: ApiClient;
  onRefresh: () => void;
  refreshing: boolean;
}

export function WorkspaceBody({ workspace, client, onRefresh, refreshing }: WorkspaceBodyProps) {
  if (workspace.task === null) {
    return (
      <section className="card empty-card" aria-live="polite">
        <p>Задача пока не назначена.</p>
        <p className="muted">
          Попросите руководителя назначить первую задачу — после этого помощник поможет с доступами и шагами.
        </p>
        <button className="btn btn-ghost" onClick={onRefresh} disabled={refreshing}>
          Обновить
        </button>
      </section>
    );
  }

  const task = workspace.task;

  return (
    <div className="workspace-grid">
      <div>
        <section className="card">
          <div className="card-label">Ваша задача</div>
          <h2 className="task-title">
            #{task.id} — {task.title}
          </h2>
          <p className="muted">{task.summary}</p>
          <div className="badge-row">
            <span className={`badge badge-access-${workspace.effectiveAccess}`} data-testid="access-badge">
              {workspace.effectiveAccess === 'denied' && <>Ресурс недоступен: {task.resourceId}</>}
              {workspace.effectiveAccess === 'granted' && <>Доступ подтверждён: {task.resourceId}</>}
              {workspace.effectiveAccess === 'unknown' && <>Доступ: неизвестно ({task.resourceId})</>}
            </span>
            {workspace.request !== null && (
              <span className={`badge badge-request-${workspace.request.status}`} data-testid="request-badge">
                Заявка {workspace.request.id} ·{' '}
                {workspace.request.status === 'pending'
                  ? 'на согласовании'
                  : workspace.request.status === 'approved'
                    ? 'одобрена'
                    : 'отклонена'}
              </span>
            )}
          </div>
          {task.instruction !== null && (
            <p>
              <a href={task.instruction.url} target="_blank" rel="noreferrer">
                {task.instruction.title}
              </a>{' '}
              <span className="muted">— разрешена для задачи</span>
            </p>
          )}
        </section>

        <ProgressCard workspace={workspace} onRefresh={onRefresh} refreshing={refreshing} />

        <ChatPanel client={client} onRefresh={onRefresh} instruction={task.instruction} />

        <NextStepCard workspace={workspace} client={client} />
      </div>

      <aside className="card side-card" aria-label="Сведения о сессии">
        <div className="card-label">Сведения</div>
        <dl className="side-list">
          <dt>Вы</dt>
          <dd>
            {workspace.user.displayName} ({workspace.user.login})
          </dd>
          <dt>Роль</dt>
          <dd>{workspace.user.role === 'trainee' ? 'стажёр' : 'демооператор'}</dd>
          <dt>Ресурс задачи</dt>
          <dd>{task.resourceName}</dd>
          <dt>Заявка</dt>
          <dd data-testid="side-request-id">{workspace.request !== null ? workspace.request.id : '—'}</dd>
        </dl>
        <button className="btn btn-primary refresh-btn" onClick={onRefresh} disabled={refreshing}>
          {refreshing ? 'Проверяем…' : 'Обновить состояние'}
        </button>
        <p className="muted small">
          Права проверяет сервер. Решение по заявке и фактическая выдача права — разные события.
        </p>
      </aside>
    </div>
  );
}
