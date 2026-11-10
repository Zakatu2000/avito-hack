import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpOperatorPanel } from './HttpOperatorPanel';

afterEach(() => vi.unstubAllGlobals());

it('sends an explicit operator decision and displays the service result', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
    requestId: 'req-01', requestStatus: 'approved', effectiveAccess: 'missing',
  })));
  vi.stubGlobal('fetch', fetch);
  render(<HttpOperatorPanel />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('Номер заявки'), 'req-01');
  await user.click(screen.getByRole('button', { name: 'Одобрить заявку' }));
  expect(await screen.findByRole('status')).toHaveTextContent('approved');
  expect(fetch.mock.calls[0][0]).toBe('/demo/requests/req-01');
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ action: 'approve' });
  expect(fetch.mock.calls[0][1].credentials).toBe('same-origin');
});

it('shows a server denial and leaves retry available', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
    message: 'Операция недоступна',
  }), { status: 403 })));
  render(<HttpOperatorPanel />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('Номер заявки'), 'foreign');
  await user.click(screen.getByRole('button', { name: 'Выдать право' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Операция недоступна');
  expect(screen.getByRole('button', { name: 'Выдать право' })).toBeEnabled();
});
