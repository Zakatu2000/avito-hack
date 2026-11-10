import type { Proposal, ServiceRequest, TaskInstruction } from '../api/types';
import type { ProposalCardState } from '../hooks/useConversation';

const statusLabels: Record<ServiceRequest['status'], string> = {
  pending: 'На согласовании',
  approved: 'Одобрена',
  rejected: 'Отклонена',
};

interface ProposalCardProps {
  proposal: Proposal;
  state: ProposalCardState;
  errorMessage: string | null;
  request: ServiceRequest | null;
  instruction: TaskInstruction | null;
  onConfirm: (proposal: Proposal) => void;
  onCancel: (proposal: Proposal) => void;
}

export function ProposalCard({
  proposal,
  state,
  errorMessage,
  request,
  instruction,
  onConfirm,
  onCancel,
}: ProposalCardProps) {
  return (
    <div className={`proposal proposal-${state}`} data-testid={`proposal-${proposal.id}`}>
      <h4>Заявка на доступ — подтвердите</h4>
      <dl className="proposal-dl">
        <dt>Ресурс</dt>
        <dd>{proposal.resource}</dd>
        <dt>Цель</dt>
        <dd>{proposal.purpose}</dd>
        <dt>Действие</dt>
        <dd>{proposal.action}</dd>
      </dl>
      {instruction !== null && (
        <p className="muted small">
          Перед подтверждением можно открыть разрешённую{' '}
          <a href={instruction.url} target="_blank" rel="noreferrer">
            {instruction.title}
          </a>
          .
        </p>
      )}
      <p className="muted small">Заявка создаётся только после вашего подтверждения. Ключ повтора не отображается.</p>

      {(state === 'open' || state === 'error') && (
        <div className="btn-row">
          <button className="btn btn-primary" onClick={() => onConfirm(proposal)}>
            Подтвердить
          </button>
          <button className="btn btn-ghost" onClick={() => onCancel(proposal)}>
            Не сейчас
          </button>
        </div>
      )}
      {state === 'confirming' && (
        <div className="btn-row">
          <button className="btn btn-primary" disabled>
            Создаём заявку…
          </button>
          <button className="btn btn-ghost" disabled>
            Не сейчас
          </button>
        </div>
      )}
      {state === 'declined' && (
        <p className="muted" data-testid={`proposal-${proposal.id}-declined`}>
          Отменено вами — заявка не создана.
        </p>
      )}
      {state === 'done' && request !== null && (
        <div className="request-result" data-testid={`proposal-${proposal.id}-result`}>
          <span className="req-id">{request.id}</span>{' '}
          <span className={`badge badge-request-${request.status}`}>{statusLabels[request.status]}</span>
        </div>
      )}
      {state === 'error' && errorMessage !== null && (
        <div className="notice notice-err" role="alert">
          {errorMessage}
        </div>
      )}
    </div>
  );
}
