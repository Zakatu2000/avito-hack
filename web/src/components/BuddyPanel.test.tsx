import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ActionPreview, BuddyClient, BuddyChatReply, ChecklistItem } from '../api/buddy';
import { BuddyPanel } from './BuddyPanel';

const axes = [
  'expertise', 'culture', 'ownership', 'business', 'agile', 'communication', 'growth', 'track',
].map((id) => ({ id, label: id, ideal: 'Описание' }));

const preview: ActionPreview = {
  actionId: 'act-123', actionType: 'escalation', label: 'Эскалация человеку',
  payload: { severity: 'blocker', to: 'mentor', summary: 'Нужна помощь' },
  idempotencyKey: 'key', confirmationToken: 'confirm', status: 'draft_preview',
  checklistItemId: null, result: null, demo: true, createdAt: '2026-11-11T10:00:00Z',
};

const item: ChecklistItem = {
  id: 'common-01', track: 'common', title: 'Организационные моменты', description: '',
  instructions: [], stage: 'week-1', stageLabel: '1 неделя', stageOrder: 1, actor: 'intern',
  status: 'available', timing: 'now', blockedBy: [], evidence: '', objective: '',
  completionPolicy: 'self_confirmed', evidenceUri: null, note: '',
  sourceRef: { sheet: 'Материалы для всех', row: 2 },
};

function createBuddyClient(): BuddyClient {
  const reply: BuddyChatReply = {
    intent: 'mentor', text: 'Подготовил черновик наставнику.',
    profile: { track: 'backend', roleCode: 'ROLE_BACKEND_E1', grade: 'E1', weekNo: 1,
      startDate: '2026-11-01', mentorName: 'Илья', curatorName: 'Мария', unit: 'Товары', stage: 'week-1' },
    progress: { total: 48, completed: 0, pct: 0 }, nextStep: null, checklistItem: null,
    sources: [], learning: null, actionPreview: preview, abstained: false, handoff: true,
    mode: 'demo', aiMode: 'demo',
  };
  const assessment = {
    id: 'wheel-123', track: 'backend', ratings: Object.fromEntries(axes.map((axis) => [axis.id, 5])),
    priorities: ['expertise'], plan: [{ axisId: 'expertise', action: 'Показать PR', dueStage: 'month-1' }],
    evidence: {}, createdAt: '2026-11-11T10:00:00Z',
  };
  return {
    bootstrap: vi.fn().mockResolvedValue({
      profile: reply.profile, progress: reply.progress, nextSteps: [], checklistCount: 48,
      aiMode: 'demo', demoIntegrations: 'mock', geminiImages: [],
    }),
    getChecklist: vi.fn().mockResolvedValue({ items: [item], progress: reply.progress, profile: reply.profile }),
    transition: vi.fn().mockResolvedValue({ item: { ...item, status: 'in_progress' }, progress: reply.progress }),
    chat: vi.fn().mockResolvedValue(reply),
    previewAction: vi.fn().mockResolvedValue({ actionPreview: preview, duplicatePreview: false }),
    confirmAction: vi.fn().mockResolvedValue({ ...preview, status: 'executed', idempotentReplay: false }),
    cancelAction: vi.fn().mockResolvedValue({ cancelled: true, actionId: preview.actionId }),
    listActions: vi.fn().mockResolvedValue({ actions: [] }),
    audit: vi.fn().mockResolvedValue({ events: [] }),
    competencyAxes: vi.fn().mockResolvedValue({ axes, scale: { min: 0, max: 10 }, source: { type: 'gemini_report' } }),
    competencyLatest: vi.fn().mockResolvedValue({ assessment: null }),
    saveCompetency: vi.fn().mockResolvedValue({ assessment }),
    sendCompetency: vi.fn().mockResolvedValue({ actionPreview: preview, duplicatePreview: false }),
    curatorHistory: vi.fn().mockResolvedValue({ messages: [] }),
  };
}

describe('BuddyPanel', () => {
  it('renders checklist, sends a chat message, and requires confirmation for the preview', async () => {
    const client = createBuddyClient();
    render(<BuddyPanel client={client} onExpired={() => undefined} />);

    expect((await screen.findAllByText('Организационные моменты')).length).toBeGreaterThan(0);
    expect(screen.getByText('Интеграции: mock · AI: demo')).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Вопрос AI-buddy'), 'Позови наставника');
    await userEvent.click(screen.getByRole('button', { name: 'Спросить' }));

    expect(await screen.findByText('Подготовил черновик наставнику.')).toBeInTheDocument();
    expect(await screen.findByRole('region', { name: 'Предпросмотр действия' })).toBeInTheDocument();
    expect(client.confirmAction).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Подтвердить действие' }));
    await waitFor(() => expect(client.confirmAction).toHaveBeenCalledWith('act-123', 'confirm', 'web-act-123'));
    expect(await screen.findByText('Выполнено в демо-контуре.')).toBeInTheDocument();
  });

  it('shows the eight-axis wheel and saves a manual assessment', async () => {
    const client = createBuddyClient();
    render(<BuddyPanel client={client} onExpired={() => undefined} />);
    expect(await screen.findByRole('img', { name: 'Радарная диаграмма самооценки по восьми компетенциям' })).toBeInTheDocument();
    expect(screen.getAllByLabelText('Зона развития')).toHaveLength(8);

    await userEvent.click(screen.getAllByLabelText('Зона развития')[0]);
    await userEvent.type(screen.getByLabelText('Действие для expertise'), 'Показать PR');
    await userEvent.click(screen.getByRole('button', { name: 'Сохранить оценку' }));
    await waitFor(() => expect(client.saveCompetency).toHaveBeenCalledWith(expect.objectContaining({
      priorities: ['expertise'], evidence: { inputMode: 'manual_no_vision_api', images: [] },
    })));
  });
});
