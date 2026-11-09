import { afterEach, describe, expect, it, vi } from 'vitest';
import { NetworkError, SessionExpiredError } from './errors';
import { HttpApiClient, readStoredSession, storeSession } from './client';
import { TestApiClient } from './testAdapter';
import {
  exampleProposal,
  exampleRequestPending,
  exampleSessionTrainee,
  exampleWorkspaceGranted,
  exampleWorkspaceInitial,
} from './fixtures';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>();

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe('HttpApiClient', () => {
  it('getWorkspace отправляет GET /workspace с токеном сессии', async () => {
    storeSession(exampleSessionTrainee);
    fetchMock.mockResolvedValue(jsonResponse(200, exampleWorkspaceInitial));
    vi.stubGlobal('fetch', fetchMock);

    const client = new HttpApiClient('/api');
    const workspace = await client.getWorkspace();

    expect(workspace.task?.id).toBe('TSK-101');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe('/api/workspace');
    expect(init?.method).toBeUndefined();
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer test-token-vasya');
  });

  it('401 превращается в SessionExpiredError и очищает сессию', async () => {
    storeSession(exampleSessionTrainee);
    fetchMock.mockResolvedValue(jsonResponse(401, { message: 'unauthorized' }));
    vi.stubGlobal('fetch', fetchMock);

    const client = new HttpApiClient();
    await expect(client.getWorkspace()).rejects.toBeInstanceOf(SessionExpiredError);
    expect(readStoredSession()).toBeNull();
  });

  it('ошибка сервера возвращает ApiError с сообщением из тела', async () => {
    fetchMock.mockResolvedValue(jsonResponse(500, { message: 'Бум' }));
    vi.stubGlobal('fetch', fetchMock);

    const client = new HttpApiClient();
    const promise = client.getWorkspace();
    await expect(promise).rejects.toMatchObject({ name: 'ApiError', status: 500, message: 'Бум' });
  });

  it('сетевой сбой превращается в NetworkError', async () => {
    fetchMock.mockRejectedValue(new TypeError('fetch failed'));
    vi.stubGlobal('fetch', fetchMock);

    const client = new HttpApiClient();
    await expect(client.getWorkspace()).rejects.toBeInstanceOf(NetworkError);
  });

  it('confirmProposal отправляет идентификатор предложения и ключ повтора', async () => {
    storeSession(exampleSessionTrainee);
    fetchMock.mockResolvedValue(jsonResponse(200, { request: exampleRequestPending, nextStep: null }));
    vi.stubGlobal('fetch', fetchMock);

    const client = new HttpApiClient();
    await client.confirmProposal('PRP-77', 'idem-REQ-2026-0142');

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe('/api/proposals/PRP-77/confirm');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toEqual({ idempotencyKey: 'idem-REQ-2026-0142' });
  });

  it('login отправляет логин и сохраняет сессию', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, exampleSessionTrainee));
    vi.stubGlobal('fetch', fetchMock);

    const client = new HttpApiClient();
    const session = await client.login('trainee-vasya');

    expect(session.user.login).toBe('trainee-vasya');
    expect(readStoredSession()?.user.login).toBe('trainee-vasya');
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe('/api/session');
    expect(JSON.parse(String(init?.body))).toEqual({ login: 'trainee-vasya' });
  });
});

describe('TestApiClient (адаптер с тем же контрактом)', () => {
  it('вход неизвестной учётной записи даёт ApiError 403', async () => {
    const client = new TestApiClient();
    await expect(client.login('hacker')).rejects.toMatchObject({ name: 'ApiError', status: 403 });
  });

  it('после входа workspace отдаёт фикстуру начального состояния', async () => {
    const client = new TestApiClient();
    await client.login('trainee-vasya');
    const workspace = await client.getWorkspace();

    expect(workspace.task?.id).toBe('TSK-101');
    expect(workspace.effectiveAccess).toBe('denied');
    expect(workspace.request).toBeNull();
  });

  it('без сессии любой запрос даёт SessionExpiredError', async () => {
    const client = new TestApiClient();
    await expect(client.getWorkspace()).rejects.toBeInstanceOf(SessionExpiredError);
  });

  it('первое сообщение — уточнение, второе — предложение с idempotencyKey', async () => {
    const client = new TestApiClient();
    await client.login('trainee-vasya');

    const first = await client.sendMessage('Не могу начать первую задачу. Что делать?');
    expect(first.type).toBe('clarification');

    const second = await client.sendMessage('Про репозиторий, он не открывается');
    expect(second.type).toBe('proposal');
    expect(second.proposal?.id).toBe(exampleProposal.id);
    expect(typeof second.proposal?.idempotencyKey).toBe('string');
  });

  it('повторное подтверждение того же предложения возвращает ту же заявку', async () => {
    const client = new TestApiClient();
    await client.login('trainee-vasya');

    const first = await client.confirmProposal(exampleProposal.id, exampleProposal.idempotencyKey);
    const second = await client.confirmProposal(exampleProposal.id, exampleProposal.idempotencyKey);

    expect(first.request.id).toBe('REQ-2026-0142');
    expect(second.request.id).toBe(first.request.id);

    const workspace = await client.getWorkspace();
    expect(workspace.request?.id).toBe('REQ-2026-0142');
    expect(workspace.request?.status).toBe('pending');
  });

  it('setDemoPhase переключает состояние workspace (для сценариев F4/F5)', async () => {
    const client = new TestApiClient();
    await client.login('trainee-vasya');

    client.setDemoPhase('granted');
    const granted = await client.getWorkspace();
    expect(granted.effectiveAccess).toBe('granted');
    expect(granted.nextStep?.code).toBe('return-to-task');
    expect(exampleWorkspaceGranted.effectiveAccess).toBe('granted');
  });

  it('подтверждение чужого предложения даёт ApiError 404', async () => {
    const client = new TestApiClient();
    await client.login('trainee-vasya');
    await expect(client.confirmProposal('PRP-OTHER', 'key')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
    });
  });
});
