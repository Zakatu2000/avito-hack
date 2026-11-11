import { useCallback, useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { SessionExpiredError } from '../api/errors';
import type { ActionPreview, BuddyBootstrap, BuddyChatReply, BuddyClient, ChecklistItem, BuddyProgress, CuratorMessage } from '../api/buddy';
import { ActionPreviewCard } from './ActionPreviewCard';
import { AuditLog } from './AuditLog';
import { CompetencyWheel } from './CompetencyWheel';

interface BuddyPanelProps {
  client: BuddyClient;
  onExpired: () => void;
}

const statusLabels: Record<string, string> = {
  available: 'Доступен', in_progress: 'В работе', evidence_pending: 'Ждёт подтверждения',
  completed: 'Выполнен', blocked: 'Заблокирован',
};

export function BuddyPanel({ client, onExpired }: BuddyPanelProps) {
  const [bootstrap, setBootstrap] = useState<BuddyBootstrap | null>(null);
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [progress, setProgress] = useState<BuddyProgress | null>(null);
  const [curatorMessages, setCuratorMessages] = useState<CuratorMessage[]>([]);
  const [chat, setChat] = useState<Array<{ role: 'user' | 'assistant'; text: string; reply?: BuddyChatReply }>>([]);
  const [draft, setDraft] = useState('');
  const [action, setAction] = useState<ActionPreview | null>(null);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const [boot, checklist, history] = await Promise.all([
        client.bootstrap(), client.getChecklist(), client.curatorHistory(),
      ]);
      setBootstrap(boot);
      setItems(checklist.items);
      setProgress(checklist.progress);
      setCuratorMessages(history.messages);
      setError(null);
    } catch (cause) {
      if (cause instanceof SessionExpiredError) { onExpired(); return; }
      setError(cause instanceof Error ? cause.message : 'Не удалось загрузить онбординг');
    } finally {
      setLoading(false);
    }
  }, [client, onExpired]);

  useEffect(() => { void reload(); }, [reload]);

  const today = useMemo(() => items.filter((item) => item.timing === 'now' || item.timing === 'overdue')
    .filter((item) => item.status !== 'completed').slice(0, 3), [items]);
  const sources = chat.at(-1)?.reply?.sources ?? [];

  async function sendChat(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    setDraft('');
    setChat((previous) => [...previous, { role: 'user', text }]);
    setSending(true);
    try {
      const reply = await client.chat(text);
      setChat((previous) => [...previous, { role: 'assistant', text: reply.text, reply }]);
      if (reply.actionPreview) setAction(reply.actionPreview);
      await reload();
    } catch (cause) {
      if (cause instanceof SessionExpiredError) onExpired();
      else setError(cause instanceof Error ? cause.message : 'Не удалось отправить сообщение');
    } finally {
      setSending(false);
    }
  }

  async function transition(item: ChecklistItem, target: 'in_progress' | 'completed' | 'evidence_pending') {
    if (item.status === 'blocked') return;
    let evidenceUri: string | undefined;
    if (target === 'completed' && (item.completionPolicy === 'evidence_required' || item.evidence)) {
      const evidence = window.prompt('Ссылка или краткий идентификатор доказательства выполнения:');
      if (!evidence?.trim()) return;
      evidenceUri = evidence.trim();
    }
    try {
      await client.transition(item.id, target, evidenceUri ? { evidenceUri } : {});
      await reload();
      setRevision((value) => value + 1);
    } catch (cause) {
      if (cause instanceof SessionExpiredError) onExpired();
      else setError(cause instanceof Error ? cause.message : 'Не удалось изменить пункт');
    }
  }

  async function prepareReminder(item: ChecklistItem) {
    try {
      const result = await client.previewAction('send_message', {
        to: item.actor === 'curator' ? 'curator' : 'mentor',
        subject: `Вопрос по пункту чек-листа: ${item.title}`,
        body: `Добрый день! Подскажите, пожалуйста, статус пункта «${item.title}» и что нужно для его завершения.`,
      }, item.id);
      setAction(result.actionPreview);
      setRevision((value) => value + 1);
    } catch (cause) {
      if (cause instanceof SessionExpiredError) onExpired();
      else setError(cause instanceof Error ? cause.message : 'Не удалось подготовить сообщение');
    }
  }

  if (loading) return <section className="card" aria-busy="true"><p role="status">Загружаем онбординг…</p></section>;
  if (bootstrap === null) return <section className="card"><p className="notice notice-err" role="alert">{error ?? 'Онбординг недоступен'}</p><button className="btn btn-primary" onClick={() => { setLoading(true); void reload(); }}>Повторить</button></section>;

  return (
    <div className="buddy-layout">
      <section className="buddy-overview" aria-label="Обзор онбординга">
        <article className="card buddy-hero">
          <div className="card-label">Онбординг · {bootstrap.profile.track}</div>
          <h2>{bootstrap.profile.roleCode} · неделя {bootstrap.profile.weekNo}</h2>
          <p className="muted">Наставник: {bootstrap.profile.mentorName} · куратор: {bootstrap.profile.curatorName}</p>
          <p className="muted small">Старт: {bootstrap.profile.startDate} · {bootstrap.profile.unit}</p>
          <p className="small muted">Интеграции: mock · AI: {bootstrap.aiMode}</p>
        </article>
        <article className="card buddy-metric">
          <div className="card-label">Прогресс</div>
          <strong className="metric-value">{progress?.pct ?? 0}%</strong>
          <progress max="100" value={progress?.pct ?? 0} aria-label="Прогресс чек-листа" />
          <p className="muted small">{progress?.completed ?? 0} из {progress?.total ?? bootstrap.checklistCount} пунктов</p>
        </article>
        <article className="card buddy-metric">
          <div className="card-label">Следующий шаг</div>
          <strong>{bootstrap.nextSteps[0]?.title ?? 'Все пункты закрыты'}</strong>
          {bootstrap.nextSteps[0] && <p className="muted small">{bootstrap.nextSteps[0].stageLabel} · {statusLabels[bootstrap.nextSteps[0].status] ?? bootstrap.nextSteps[0].status}</p>}
        </article>
      </section>

      {error && <p className="notice notice-err" role="alert">{error}</p>}

      <section className="card" aria-labelledby="today-title">
        <div className="card-label" id="today-title">Сегодня и просроченные шаги</div>
        {today.length === 0 ? <p className="muted">На этом этапе срочных шагов нет.</p> : (
          <ul className="today-list">{today.map((item) => <li key={item.id}><strong>{item.title}</strong><span className="muted"> · {item.timing === 'overdue' ? 'Рекомендуется пройти' : item.stageLabel}</span></li>)}</ul>
        )}
      </section>

      <section className="card" aria-labelledby="checklist-title">
        <div className="card-label" id="checklist-title">Чек-лист · {items.length} пунктов</div>
        <div className="checklist-list">
          {items.map((item) => (
            <article className={`checklist-item checklist-${item.status}`} key={item.id}>
              <div className="checklist-item-main">
                <div className="checklist-title-row"><strong>{item.title}</strong><span className={`status-pill status-${item.status}`}>{statusLabels[item.status]}</span></div>
                <p className="muted small">{item.stageLabel} · {item.actor === 'intern' ? 'стажёр' : item.actor} · {item.track}</p>
                {item.description && <p>{item.description}</p>}
                {item.blockedBy.length > 0 && <p className="notice notice-warn small">Сначала: {item.blockedBy.join(', ')}</p>}
                {item.instructions.length > 0 && <details><summary>Инструкция</summary><ul>{item.instructions.map((line, index) => <li key={index}>{line}</li>)}</ul></details>}
                {item.evidence && <p className="small"><strong>Доказательство:</strong> {item.evidence}</p>}
              </div>
              <div className="checklist-actions">
                {item.status === 'available' && <button className="btn btn-ghost" onClick={() => void transition(item, 'in_progress')}>Начать</button>}
                {item.status === 'in_progress' && item.actor === 'intern' && item.completionPolicy !== 'curator_confirmed' && (
                  <>
                    {item.completionPolicy === 'evidence_required' && <button className="btn btn-ghost" onClick={() => void transition(item, 'evidence_pending')}>Передать доказательство</button>}
                    <button className="btn btn-primary" onClick={() => void transition(item, 'completed')}>Завершить</button>
                  </>
                )}
                {item.status === 'in_progress' && item.actor !== 'intern' && <button className="btn btn-ghost" onClick={() => void prepareReminder(item)}>Напомнить человеку</button>}
                {item.status === 'evidence_pending' && item.actor === 'intern' && item.completionPolicy !== 'curator_confirmed' && (
                  <button className="btn btn-primary" onClick={() => void transition(item, 'completed')}>Подтвердить выполнение</button>
                )}
                {item.status === 'evidence_pending' && (item.actor !== 'intern' || item.completionPolicy === 'curator_confirmed') && <span className="muted small">Ждёт проверки наставником/куратором</span>}
                {item.completionPolicy === 'curator_confirmed' && item.status !== 'completed' && <span className="muted small">Завершает куратор</span>}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="card chat-card" aria-labelledby="buddy-chat-title">
        <div className="card-label" id="buddy-chat-title">AI-buddy · вопрос или ответ куратора</div>
        <div className="chat-log" role="log" aria-live="polite">
          {chat.length === 0 && <div className="msg msg-bot">Могу подсказать следующий шаг, найти материал или разобрать сообщение куратора. Ответы из базы сопровождаются источниками.</div>}
          {chat.map((message, index) => (
            <div className={`msg ${message.role === 'user' ? 'msg-user' : 'msg-bot'}`} key={index}>
              <p className="msg-text">{message.text}</p>
              {message.reply?.abstained && <span className="msg-tag">Не найдено в одобренной базе</span>}
              {message.reply?.learning?.kind === 'curator_breakdown' && <span className="msg-tag">Разбор ответа куратора</span>}
            </div>
          ))}
          {sending && <div className="msg msg-bot" role="status">Помощник готовит ответ…</div>}
        </div>
        {sources.length > 0 && <div className="source-list" aria-label="Источники ответа">
          <strong>Источники</strong>{sources.map((source) => <details key={source.chunkId}>
            <summary>{source.title} · {source.section} <span className="muted">({source.tier})</span></summary>
            <blockquote>{source.quote}</blockquote><p className="small muted">{source.sourceStatus} · {source.freshness}</p>
          </details>)}
        </div>}
        <form className="chat-input" onSubmit={(event) => void sendChat(event)}>
          <input value={draft} onChange={(event) => setDraft(event.target.value)}
            aria-label="Вопрос AI-buddy" placeholder="Например: что дальше? / куратор ответил: …" disabled={sending} />
          <button className="btn btn-primary" type="submit" disabled={sending || !draft.trim()}>Спросить</button>
        </form>
      </section>

      {action && <ActionPreviewCard action={action} client={client} onChanged={() => {
        setRevision((value) => value + 1); void reload();
      }} />}

      <CompetencyWheel client={client} imageEvidence={bootstrap.geminiImages.map(({ file, sha256 }) => ({ file, sha256 }))}
        onPreview={(preview) => { setAction(preview); setRevision((value) => value + 1); }} />

      <section className="card" aria-labelledby="fixture-preview-title">
        <div className="card-label" id="fixture-preview-title">Материалы Gemini · извлечённый контекст</div>
        <p className="muted small">Изображения DOCX доступны офлайн; оценки вводятся вручную, Vision API не вызывается.</p>
        <div className="fixture-grid">
          {bootstrap.geminiImages.map((image) => (
            <figure key={image.file}>
              <a href={`/api/buddy/gemini/images/${encodeURIComponent(image.file)}`} target="_blank" rel="noreferrer">
                <img src={`/api/buddy/gemini/images/${encodeURIComponent(image.file)}`} alt={image.altText} loading="lazy" />
              </a>
              <figcaption>{image.altText}<code>SHA-256 · {image.sha256}</code></figcaption>
            </figure>
          ))}
        </div>
        <details><summary>Что извлечено</summary>
          <p>Документ содержит упражнение: выбрать направление аналитики, оценить ровно 8 компетенций по шкале 0–10, отметить 1–2 зоны роста и составить план действий со сроками. Загрузка и заполнение работают без vision-провайдера.</p>
        </details>
      </section>

      <section className="card" aria-labelledby="curator-history-title">
        <div className="card-label" id="curator-history-title">Сообщения куратора и buddy</div>
        {curatorMessages.length === 0 ? <p className="muted">Сообщений пока нет. Вставьте ответ куратора в чат — buddy выделит решения, ограничения и вопросы.</p> : (
          <ol className="curator-history">{curatorMessages.map((message) => <li key={message.id}>
            <span className="status-pill">{message.direction === 'in' ? 'Входящее' : 'Черновик/отправлено'}</span>
            <p>{message.body}</p>
            {message.parsed && <pre>{JSON.stringify(message.parsed, null, 2)}</pre>}
          </li>)}</ol>
        )}
      </section>

      <AuditLog client={client} revision={revision} />
    </div>
  );
}
