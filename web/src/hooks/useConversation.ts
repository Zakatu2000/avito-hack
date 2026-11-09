import { useCallback, useState } from 'react';
import { NetworkError } from '../api/errors';
import type { ApiClient, MessageResultType, Proposal, ServiceRequest } from '../api/types';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  kind: MessageResultType | 'request-created' | 'error';
  text: string;
  source: string | null;
  proposal: Proposal | null;
  request: ServiceRequest | null;
}

export type ProposalCardState = 'open' | 'confirming' | 'done' | 'declined' | 'error';

let uid = 0;

const requestStatusText: Record<ServiceRequest['status'], string> = {
  pending: 'на согласовании',
  approved: 'одобрена',
  rejected: 'отклонена',
};

interface UseConversationOptions {
  client: ApiClient;
  onServerStateChanged: () => Promise<void> | void;
}

export function useConversation({ client, onServerStateChanged }: UseConversationOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [cardStates, setCardStates] = useState<Record<string, ProposalCardState>>({});
  const [confirmError, setConfirmError] = useState<{ proposalId: string; message: string } | null>(null);

  const append = useCallback((message: Omit<ChatMessage, 'id'>) => {
    uid += 1;
    const withId = { ...message, id: `m${uid}` };
    setMessages((prev) => [...prev, withId]);
    return withId.id;
  }, []);

  const setCardState = useCallback((proposalId: string, state: ProposalCardState) => {
    setCardStates((prev) => ({ ...prev, [proposalId]: state }));
  }, []);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (trimmed.length === 0 || sending) return;
      append({ role: 'user', kind: 'text', text: trimmed, source: null, proposal: null, request: null });
      setSending(true);
      try {
        const reply = await client.sendMessage(trimmed);
        append({
          role: 'assistant',
          kind: reply.type,
          text: reply.text,
          source: reply.source,
          proposal: reply.proposal,
          request: reply.request,
        });
        if (reply.request !== null) await onServerStateChanged();
      } catch (error) {
        if (error instanceof NetworkError) await onServerStateChanged();
        append({
          role: 'assistant',
          kind: 'error',
          text: 'Не получилось связаться с сервером. Показываю состояние из последнего ответа.',
          source: null,
          proposal: null,
          request: null,
        });
      } finally {
        setSending(false);
      }
    },
    [append, client, onServerStateChanged, sending],
  );

  const confirm = useCallback(
    async (proposal: Proposal) => {
      if (Object.values(cardStates).includes('confirming')) return;
      setConfirmError(null);
      setCardState(proposal.id, 'confirming');
      try {
        const result = await client.confirmProposal(proposal.id, proposal.idempotencyKey);
        setCardState(proposal.id, 'done');
        append({
          role: 'assistant',
          kind: 'request-created',
          text: `Заявка создана: ${result.request.id} — ${requestStatusText[result.request.status]}.`,
          source: 'результат сервиса заявок',
          proposal: null,
          request: result.request,
        });
        await onServerStateChanged();
      } catch (error) {
        if (error instanceof NetworkError) await onServerStateChanged();
        setConfirmError({
          proposalId: proposal.id,
          message: error instanceof Error ? error.message : 'Не удалось подтвердить',
        });
        setCardState(proposal.id, 'error');
      }
    },
    [append, cardStates, client, onServerStateChanged, setCardState],
  );

  const cancel = useCallback(
    (proposal: Proposal) => {
      setCardState(proposal.id, 'declined');
      append({
        role: 'assistant',
        kind: 'text',
        text: 'Хорошо, заявку не создаём. Когда решите — спросите снова.',
        source: null,
        proposal: null,
        request: null,
      });
    },
    [append, setCardState],
  );

  return { messages, sending, cardStates, confirmError, send, confirm, cancel };
}
