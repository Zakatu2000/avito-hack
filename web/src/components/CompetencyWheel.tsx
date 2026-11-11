import { useEffect, useMemo, useState } from 'react';
import type { BuddyClient, CompetencyAssessment, CompetencyAxis, CompetencyPlanEntry, ActionPreview } from '../api/buddy';

const dueStages = [
  ['week-1', '1 неделя'], ['week-2', '2 неделя'], ['month-1', '1 месяц'],
  ['month-2', '2 месяц'], ['month-3', '3 месяц'], ['after-month-3', 'После 3 месяцев'],
];

interface CompetencyWheelProps {
  client: BuddyClient;
  onPreview: (preview: ActionPreview) => void;
  imageEvidence?: Array<{ file: string; sha256: string }>;
}

export function CompetencyWheel({ client, onPreview, imageEvidence = [] }: CompetencyWheelProps) {
  const [axes, setAxes] = useState<CompetencyAxis[]>([]);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [priorities, setPriorities] = useState<string[]>([]);
  const [plan, setPlan] = useState<Record<string, { action: string; dueStage: string }>>({});
  const [assessment, setAssessment] = useState<CompetencyAssessment | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    Promise.all([client.competencyAxes(), client.competencyLatest()])
      .then(([axisReply, latest]) => {
        if (ignore) return;
        setAxes(axisReply.axes);
        setAssessment(latest.assessment);
        if (latest.assessment) {
          setRatings(latest.assessment.ratings);
          setPriorities(latest.assessment.priorities);
          setPlan(Object.fromEntries(latest.assessment.plan.map((entry) => [entry.axisId, {
            action: entry.action, dueStage: entry.dueStage,
          }])));
        } else {
          setRatings(Object.fromEntries(axisReply.axes.map((axis) => [axis.id, 5])));
        }
      })
      .catch((cause: unknown) => {
        if (!ignore) setNotice(cause instanceof Error ? cause.message : 'Не удалось загрузить колесо');
      });
    return () => { ignore = true; };
  }, [client]);

  const points = useMemo(() => {
    const center = 120;
    const radius = 82;
    return axes.map((axis, index) => {
      const angle = -Math.PI / 2 + (2 * Math.PI * index) / Math.max(axes.length, 1);
      const value = Math.max(0, Math.min(10, ratings[axis.id] ?? 0)) / 10;
      return {
        id: axis.id,
        x: center + Math.cos(angle) * radius * value,
        y: center + Math.sin(angle) * radius * value,
        ax: center + Math.cos(angle) * radius,
        ay: center + Math.sin(angle) * radius,
      };
    });
  }, [axes, ratings]);

  function togglePriority(id: string) {
    setPriorities((previous) => previous.includes(id)
      ? previous.filter((value) => value !== id)
      : previous.length < 2 ? [...previous, id] : previous);
  }

  async function save() {
    setBusy(true);
    setNotice(null);
    try {
      const entries: CompetencyPlanEntry[] = priorities.map((axisId) => ({
        axisId,
        action: plan[axisId]?.action?.trim() ?? '',
        dueStage: plan[axisId]?.dueStage ?? 'month-1',
      }));
      const result = await client.saveCompetency({ ratings, priorities, plan: entries,
        evidence: { inputMode: 'manual_no_vision_api', images: imageEvidence } });
      setAssessment(result.assessment);
      setNotice('Самооценка сохранена. План куратору можно отправить через предпросмотр.');
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : 'Не удалось сохранить оценку');
    } finally {
      setBusy(false);
    }
  }

  async function sendPlan() {
    if (!assessment) return;
    setBusy(true);
    setNotice(null);
    try {
      const result = await client.sendCompetency(assessment.id);
      onPreview(result.actionPreview);
      setNotice('Создан черновик. Отправка произойдёт только после явного подтверждения.');
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : 'Не удалось подготовить план');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card competency-card" aria-labelledby="competency-title">
      <div className="card-label" id="competency-title">Колесо компетенций · шкала 0–10</div>
      <p className="muted small">Оцените все 8 осей самостоятельно. Vision API не требуется; изображение используется как справочный материал.</p>
      {notice && <p className="notice notice-warn" role="status">{notice}</p>}
      {axes.length === 0 ? <p className="muted">Загружаем оси…</p> : (
        <>
          <svg className="competency-radar" viewBox="0 0 240 240" role="img" aria-label="Радарная диаграмма самооценки по восьми компетенциям">
            {[0.25, 0.5, 0.75, 1].map((level) => (
              <polygon key={level} points={axes.map((_, index) => {
                const angle = -Math.PI / 2 + (2 * Math.PI * index) / axes.length;
                return `${120 + Math.cos(angle) * 82 * level},${120 + Math.sin(angle) * 82 * level}`;
              }).join(' ')} className="radar-grid" />
            ))}
            {points.map((point) => <line key={`line-${point.id}`} x1="120" y1="120" x2={point.ax} y2={point.ay} className="radar-axis" />)}
            <polygon points={points.map((point) => `${point.x},${point.y}`).join(' ')} className="radar-value" />
            {points.map((point) => <circle key={point.id} cx={point.x} cy={point.y} r="3" className="radar-dot" />)}
          </svg>
          <div className="competency-axis-list">
            {axes.map((axis) => (
              <div className="competency-axis" key={axis.id}>
                <label htmlFor={`rating-${axis.id}`}><strong>{axis.label}</strong>
                  <span className="muted small">{axis.ideal}</span>
                </label>
                <input id={`rating-${axis.id}`} type="range" min="0" max="10" step="1"
                  value={ratings[axis.id] ?? 0}
                  onChange={(event) => setRatings((current) => ({ ...current, [axis.id]: Number(event.target.value) }))} />
                <output htmlFor={`rating-${axis.id}`}>{ratings[axis.id] ?? 0}/10</output>
                <label className="priority-toggle">
                  <input type="checkbox" checked={priorities.includes(axis.id)}
                    disabled={!priorities.includes(axis.id) && priorities.length >= 2}
                    onChange={() => togglePriority(axis.id)} />
                  Зона развития
                </label>
                {priorities.includes(axis.id) && (
                  <div className="plan-fields">
                    <input aria-label={`Действие для ${axis.label}`} placeholder="Конкретное действие"
                      value={plan[axis.id]?.action ?? ''}
                      onChange={(event) => setPlan((current) => ({ ...current,
                        [axis.id]: { action: event.target.value, dueStage: current[axis.id]?.dueStage ?? 'month-1' } }))} />
                    <select aria-label={`Срок для ${axis.label}`} value={plan[axis.id]?.dueStage ?? 'month-1'}
                      onChange={(event) => setPlan((current) => ({ ...current,
                        [axis.id]: { action: current[axis.id]?.action ?? '', dueStage: event.target.value } }))}>
                      {dueStages.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                    </select>
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="btn-row">
            <button className="btn btn-primary" disabled={busy || priorities.length === 0}
              onClick={() => void save()}>{busy ? 'Сохраняем…' : 'Сохранить оценку'}</button>
            <button className="btn btn-ghost" disabled={busy || !assessment}
              onClick={() => void sendPlan()}>Подготовить план куратору</button>
          </div>
        </>
      )}
    </section>
  );
}
