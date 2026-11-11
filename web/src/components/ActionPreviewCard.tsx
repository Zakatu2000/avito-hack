import { useState } from 'react';
import type { ActionPreview, BuddyClient } from '../api/buddy';

interface ActionPreviewCardProps {
  action: ActionPreview;
  client: BuddyClient;
  onChanged: () => void;
}

export function ActionPreviewCard({ action, client, onChanged }: ActionPreviewCardProps) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [state, setState] = useState(action.status);

  async function confirm() {
    setBusy(true);
    setMessage(null);
    try {
      const result = await client.confirmAction(action.actionId, action.confirmationToken,
        `web-${action.actionId}`);
      setState(result.status);
      setMessage(result.idempotentReplay ? 'Результат уже был выполнен ранее.' : 'Выполнено в демо-контуре.');
      onChanged();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : 'Не удалось выполнить действие');
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    setBusy(true);
    setMessage(null);
    try {
      await client.cancelAction(action.actionId);
      setState('cancelled');
      setMessage('Черновик отменён.');
      onChanged();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : 'Не удалось отменить');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="action-preview" aria-label="Предпросмотр действия">
      <div className="action-preview-head">
        <strong>{action.label}</strong>
        <span className="badge badge-request-pending">{state === 'draft_preview' ? 'Черновик' : state}</span>
      </div>
      <dl className="proposal-dl">
        {Object.entries(action.payload).map(([key, value]) => (
          <div className="action-field" key={key}><dt>{key}</dt><dd>{value}</dd></div>
        ))}
      </dl>
      <p className="muted small">Действие не отправляется без явного подтверждения. Контур: mock.</p>
      {state === 'draft_preview' && (
        <div className="btn-row">
          <button className="btn btn-primary" disabled={busy} onClick={() => void confirm()}>
            {busy ? 'Обрабатываем…' : 'Подтвердить действие'}
          </button>
          <button className="btn btn-ghost" disabled={busy} onClick={() => void cancel()}>Отменить</button>
        </div>
      )}
      {message && <p className="small" role="status">{message}</p>}
    </section>
  );
}
