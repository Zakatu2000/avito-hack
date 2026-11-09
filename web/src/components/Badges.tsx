import type { AccessState, RequestStatus } from '../api/types';

const accessLabels: Record<AccessState, string> = {
  denied: 'Ресурс недоступен',
  granted: 'Доступ подтверждён',
  unknown: 'Доступ: неизвестно',
};

const requestLabels: Record<RequestStatus, string> = {
  pending: 'Заявка на согласовании',
  approved: 'Заявка одобрена',
  rejected: 'Заявка отклонена',
};

export function AccessBadge({ state }: { state: AccessState }) {
  return (
    <span className={`badge badge-access-${state}`} data-testid="access-badge">
      {accessLabels[state]}
    </span>
  );
}

export function RequestBadge({ status }: { status: RequestStatus }) {
  return (
    <span className={`badge badge-request-${status}`} data-testid="request-badge">
      {requestLabels[status]}
    </span>
  );
}
