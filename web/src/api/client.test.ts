import { afterEach, describe, expect, it, vi } from 'vitest';
import { NetworkError, SessionExpiredError } from './errors';
import { HttpApiClient, readStoredSession, storeSession } from './client';
import { TestApiClient } from './testAdapter';
import {
  exampleProposal,
  exampleSessionTrainee,
  exampleWorkspaceGranted,
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
  const identity = { user: exampleSessionTrainee.user, aiMode: 'demo', demoOperator: true };
  const wire = { task: { taskId: 'task-01', title: 'README', resourceId: 'repo-intro' },
    source: null, effectiveAccess: 'missing', request: null, nextStep: 'Запросите доступ' };
  it('использует cookie и преобразует серверные поля', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, identity)).mockResolvedValueOnce(jsonResponse(200, wire));
    vi.stubGlobal('fetch', fetchMock);
    const workspace = await new HttpApiClient().getWorkspace();
    expect(workspace.task?.id).toBe('task-01');
    expect(workspace.effectiveAccess).toBe('denied');
    for (const [, init] of fetchMock.mock.calls) {
      expect(init?.credentials).toBe('same-origin');
      expect(new Headers(init?.headers).has('Authorization')).toBe(false);
    }
  });
  it('подтверждает пустым POST с ключом в заголовке', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, identity)).mockResolvedValueOnce(jsonResponse(200,
      { ...wire, request: { requestId: 'req-01', requestStatus: 'pending' } }));
    vi.stubGlobal('fetch', fetchMock);
    const result = await new HttpApiClient().confirmProposal('prop-01', 'stable-key');
    expect(result.request.id).toBe('req-01');
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe('/api/proposals/prop-01/confirm');
    expect(init?.body).toBeUndefined();
    expect(new Headers(init?.headers).get('Idempotency-Key')).toBe('stable-key');
  });
  it('входит с учебным паролем, хранит метаданные без bearer token', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, wire)).mockResolvedValueOnce(jsonResponse(200, identity));
    vi.stubGlobal('fetch', fetchMock);
    await new HttpApiClient().login('intern-demo');
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ username:'intern-demo',password:'training-only' });
    expect(readStoredSession()?.token).toBe('');
  });
  it('401 удаляет локальные метаданные', async () => {
    storeSession(exampleSessionTrainee);
    fetchMock.mockResolvedValue(jsonResponse(401, {}));
    vi.stubGlobal('fetch', fetchMock);
    await expect(new HttpApiClient().getWorkspace()).rejects.toBeInstanceOf(SessionExpiredError);
    expect(readStoredSession()).toBeNull();
  });
  it('сетевой сбой даёт NetworkError', async () => {
    fetchMock.mockRejectedValue(new TypeError('offline'));
    vi.stubGlobal('fetch', fetchMock);
    await expect(new HttpApiClient().getWorkspace()).rejects.toBeInstanceOf(NetworkError);
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
