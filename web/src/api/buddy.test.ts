import { afterEach, describe, expect, it, vi } from 'vitest';
import { HttpBuddyClient } from './buddy';
import { SessionExpiredError } from './errors';

const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>();

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe('HttpBuddyClient', () => {
  it('создаёт preview и подтверждает его с idempotency key', async () => {
    const action = { actionId: 'act-1', actionType: 'send_message', status: 'draft_preview' };
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { actionPreview: action, duplicatePreview: false }))
      .mockResolvedValueOnce(jsonResponse(200, { ...action, status: 'executed', idempotentReplay: false }));
    vi.stubGlobal('fetch', fetchMock);
    const client = new HttpBuddyClient();
    await client.previewAction('send_message', { to: 'mentor', subject: 'Вопрос', body: 'Привет' }, 'common-01');
    await client.confirmAction('act-1', 'token', 'stable-key');

    expect(fetchMock.mock.calls[0][0]).toBe('/api/buddy/actions/preview');
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      actionType: 'send_message', payload: { to: 'mentor', subject: 'Вопрос', body: 'Привет' },
      checklistItemId: 'common-01',
    });
    expect(fetchMock.mock.calls[1][0]).toBe('/api/buddy/actions/act-1/confirm');
    expect(new Headers(fetchMock.mock.calls[1][1]?.headers).get('Idempotency-Key')).toBe('stable-key');
    expect(fetchMock.mock.calls[1][1]?.credentials).toBe('same-origin');
  });

  it('401 очищает метаданные сессии и отдаёт session-expired ошибку', async () => {
    window.localStorage.setItem('aibuddy.session', JSON.stringify({ token: '', user: { login: 'intern-demo', role: 'trainee' } }));
    fetchMock.mockResolvedValue(jsonResponse(401, {}));
    vi.stubGlobal('fetch', fetchMock);
    await expect(new HttpBuddyClient().bootstrap()).rejects.toBeInstanceOf(SessionExpiredError);
    expect(window.localStorage.getItem('aibuddy.session')).toBeNull();
  });
});
