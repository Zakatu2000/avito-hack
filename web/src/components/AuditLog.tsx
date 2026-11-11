import { useEffect, useState } from 'react';
import type { AuditEvent, BuddyClient } from '../api/buddy';

export function AuditLog({ client, revision }: { client: BuddyClient; revision: number }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    client.audit().then((data) => { if (!ignore) { setEvents(data.events); setError(null); } })
      .catch((cause: unknown) => {
        if (!ignore) setError(cause instanceof Error ? cause.message : 'Аудит недоступен');
      });
    return () => { ignore = true; };
  }, [client, revision]);

  return (
    <section className="card" aria-labelledby="audit-title">
      <div className="card-label" id="audit-title">Журнал действий</div>
      {error && <p className="notice notice-warn" role="status">{error}</p>}
      {!error && events.length === 0 && <p className="muted">Пока нет событий аудита.</p>}
      <ol className="audit-list">
        {events.map((event) => (
          <li key={event.id}>
            <span className="audit-event">{event.event}</span>
            {event.actionId && <span className="muted"> · {event.actionId}</span>}
            <time className="muted" dateTime={event.at}>{new Date(event.at).toLocaleString()}</time>
          </li>
        ))}
      </ol>
    </section>
  );
}
