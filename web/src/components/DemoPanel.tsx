import { useState } from 'react';
import type { ApiClient } from '../api/types';
import { TestApiClient } from '../api/testAdapter';
import type { DemoPhase } from '../api/testAdapter';

export function DemoPanel({ client }: { client: ApiClient }) {
  const [lastAction, setLastAction] = useState<string | null>(null);
  const demo = client instanceof TestApiClient ? client : null;

  if (demo === null) {
    return null;
  }

  const apply = (phase: DemoPhase, label: string) => {
    demo.setDemoPhase(phase);
    setLastAction(label);
  };

  return (
    <section className="card demo-panel" data-testid="demo-panel">
      <div className="card-label">Демооператор · имитатор согласования</div>
      <p className="muted small">
        Учебный инструмент тестового режима. В живой сборке эти действия выполняет сервис заявок (Web 2, B5).
        Одобрение заявки и выдача права — отдельные шаги.
      </p>
      <div className="btn-row">
        <button className="btn btn-primary" onClick={() => apply('approved', 'Заявка одобрена (право не выдано)')}>
          Одобрить заявку
        </button>
        <button className="btn btn-ok" onClick={() => apply('granted', 'Право выдано')}>
          Выдать право
        </button>
        <button className="btn btn-ghost" onClick={() => apply('rejected', 'Заявка отклонена')}>
          Отклонить
        </button>
        <button
          className="btn btn-ghost"
          onClick={() => apply('granted-direct', 'Право уже выдано (без заявки)')}
        >
          Право без заявки
        </button>
        <button
          className="btn btn-ghost"
          onClick={() => {
            demo.resetDemo();
            setLastAction('Демоданные сброшены');
          }}
        >
          Сброс демо
        </button>
      </div>
      {lastAction !== null && (
        <p className="notice notice-ok" role="status" data-testid="demo-panel-last">
          {lastAction}
        </p>
      )}
    </section>
  );
}
