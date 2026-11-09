import type { Workspace } from '../api/types';

interface WorkspaceBodyProps {
  workspace: Workspace;
  onRefresh: () => void;
  refreshing: boolean;
}

export function WorkspaceBody({ workspace, onRefresh, refreshing }: WorkspaceBodyProps) {
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
              {workspace.effectiveAccess === 'unknown' && <>Доступ: неизвестно</>}
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

        {workspace.nextStep !== null && (
          <section className="card" aria-labelledby="next-step-title">
            <div className="card-label">Следующий шаг</div>
            <h3 id="next-step-title">{workspace.nextStep.title}</h3>
            <ul>
              {workspace.nextStep.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        )}
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
          <dd>{workspace.request !== null ? workspace.request.id : '—'}</dd>
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
