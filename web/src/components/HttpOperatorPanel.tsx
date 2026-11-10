import { useState } from 'react';

export function HttpOperatorPanel() {
  const [id, setId] = useState('');
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);

  async function act(action: string) {
    setBusy(true);
    try {
      const response = await fetch('/demo/requests/' + encodeURIComponent(id), {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message ?? 'Ошибка демосервиса');
      setStatus(`Заявка ${result.requestId}: ${result.requestStatus}. Доступ: ${result.effectiveAccess}.`);
    } catch (error) { setStatus(error instanceof Error ? error.message : 'Сервис недоступен'); }
    finally { setBusy(false); }
  }

  return <section className="card">
    <h2>Демооператор · корпоративный сервис</h2>
    <p>Скопируйте номер заявки из сессии стажёра. Одобрите заявку, затем отдельно выдайте право.</p>
    <label>Номер заявки <input aria-label="Номер заявки" value={id} onChange={e => setId(e.target.value)} /></label>
    <div className="btn-row">
      <button className="btn btn-primary" disabled={busy || !id} onClick={() => void act('approve')}>Одобрить заявку</button>
      <button className="btn btn-ok" disabled={busy || !id} onClick={() => void act('grant')}>Выдать право</button>
      <button className="btn btn-ghost" disabled={busy || !id} onClick={() => void act('reject')}>Отклонить</button>
    </div>
    <p role="status">{status}</p>
  </section>;
}
