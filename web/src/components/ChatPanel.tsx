import { useState } from 'react';
import { useConversation } from '../hooks/useConversation';
import { ProposalCard } from './ProposalCard';
import type { ApiClient, TaskInstruction } from '../api/types';

interface ChatPanelProps {
  client: ApiClient;
  onRefresh: () => Promise<void> | void;
  instruction: TaskInstruction | null;
}

export function ChatPanel({ client, onRefresh, instruction }: ChatPanelProps) {
  const { messages, sending, cardStates, confirmError, send, confirm, cancel } = useConversation({
    client,
    onServerStateChanged: onRefresh,
  });
  const [draft, setDraft] = useState('');

  async function handleSend() {
    const text = draft;
    setDraft('');
    await send(text);
  }

  const lastRequest = [...messages].reverse().find((m) => m.request !== null)?.request ?? null;

  return (
    <section className="card chat-card" aria-labelledby="chat-title">
      <div className="card-label" id="chat-title">
        Вопрос помощнику
      </div>

      {messages.length === 0 && (
        <div className="msg msg-bot">
          Здравствуйте! Опишите проблему своими словами — я проверю назначение задачи и доступ.
        </div>
      )}

      <div className="chat-log" role="log" aria-live="polite">
        {messages.map((message) => (
          <div key={message.id} className={`msg ${message.role === 'user' ? 'msg-user' : 'msg-bot'}`}>
            <p className="msg-text">{message.text}</p>
            {message.kind === 'error' && <span className="msg-tag msg-tag-err">ошибка связи</span>}
            {message.kind === 'clarification' && <span className="msg-tag">уточнение</span>}
            {message.source !== null && message.role === 'assistant' && (
              <span className="msg-src">Источник: {message.source}</span>
            )}
            {message.proposal !== null && (
              <ProposalCard
                proposal={message.proposal}
                state={cardStates[message.proposal.id] ?? 'open'}
                errorMessage={confirmError !== null && confirmError.proposalId === message.proposal.id ? confirmError.message : null}
                request={message.request ?? lastRequest}
                instruction={instruction}
                onConfirm={(p) => void confirm(p)}
                onCancel={cancel}
              />
            )}
          </div>
        ))}
        {sending && (
          <div className="msg msg-bot" data-testid="assistant-thinking">
            <div className="skeleton skeleton-chat" />
            Помощник проверяет…
          </div>
        )}
      </div>

      <form
        className="chat-input"
        onSubmit={(event) => {
          event.preventDefault();
          void handleSend();
        }}
      >
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Например: не могу открыть репозиторий задачи…"
          aria-label="Текст вопроса"
          disabled={sending}
        />
        <button type="submit" className="btn btn-primary" disabled={sending || draft.trim().length === 0}>
          {sending ? 'Отправляем…' : 'Спросить'}
        </button>
      </form>
    </section>
  );
}
