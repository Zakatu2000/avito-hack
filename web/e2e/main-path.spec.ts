import { expect, test, type Page } from '@playwright/test';

const TRAINEE = 'Войти как Вася Стажёр';
const OPERATOR = 'Войти как Демооператор';

async function cleanSession(page: Page) {
  await page.goto('/');
  await page.evaluate(() => window.localStorage.clear());
  await page.reload();
}

async function loginAs(page: Page, label: string) {
  await page.getByRole('button', { name: label }).click();
}

async function ask(page: Page, text: string) {
  await page.getByLabel('Текст вопроса').fill(text);
  await page.getByRole('button', { name: 'Спросить' }).click();
}

async function switchTo(page: Page, label: string) {
  await page.getByRole('button', { name: 'Выйти' }).click();
  await loginAs(page, label);
}

async function createRequest(page: Page) {
  await loginAs(page, TRAINEE);
  await expect(page.getByText('Настроить CI для учебного сервиса')).toBeVisible();
  await ask(page, 'Не могу начать первую задачу. Что делать?');
  await expect(page.getByText(/Уточню, чтобы помочь точно/)).toBeVisible();
  await ask(page, 'Про репозиторий, он не открывается');
  await expect(page.getByTestId('proposal-PRP-77')).toBeVisible();
  await page.getByRole('button', { name: 'Подтвердить' }).click();
  await expect(page.getByText(/Заявка создана: REQ-2026-0142/)).toBeVisible();
}

test.describe('сквозной путь глазами жюри', () => {
  test('основной сценарий: вопрос → заявка → перезагрузка → одобрение → право → следующий шаг', async ({ page }) => {
    await cleanSession(page);
    await createRequest(page);

    await expect(page.getByTestId('progress-request-id')).toHaveText('REQ-2026-0142');
    await expect(page.getByTestId('decision-badge')).toHaveText('На согласовании');

    await page.reload();
    await expect(page.getByTestId('progress-request-id')).toHaveText('REQ-2026-0142');

    await ask(page, 'Что-то всё равно не открывается, я уже спрашивал');
    await expect(page.getByText(/REQ-2026-0142 — на согласовании/)).toBeVisible();
    await expect(page.getByTestId('proposal-PRP-77')).toHaveCount(0);

    await switchTo(page, OPERATOR);
    await expect(page.getByTestId('demo-panel')).toBeVisible();
    await page.getByTestId('demo-panel').getByRole('button', { name: 'Одобрить заявку' }).click();
    await expect(page.getByTestId('demo-panel-last')).toContainText('одобрена');

    await switchTo(page, TRAINEE);
    await expect(page.getByTestId('decision-badge')).toHaveText('Одобрена');
    await expect(page.getByTestId('wait-access-note')).toBeVisible();
    await expect(page.getByTestId('return-to-task')).toHaveCount(0);

    await switchTo(page, OPERATOR);
    await page.getByTestId('demo-panel').getByRole('button', { name: 'Выдать право' }).click();
    await expect(page.getByTestId('demo-panel-last')).toContainText('Право выдано');

    await switchTo(page, TRAINEE);
    await page.getByRole('button', { name: 'Обновить состояние' }).first().click();
    await expect(page.getByTestId('progress-access-badge')).toHaveText('Подтверждён сервером');
    await expect(page.getByTestId('return-to-task')).toBeVisible();
    await page.getByTestId('return-to-task').click();
    await expect(page.getByTestId('return-recorded')).toBeVisible();
  });

  test('после отказа закрытые сведения не появляются', async ({ page }) => {
    await cleanSession(page);
    await createRequest(page);

    await switchTo(page, OPERATOR);
    await page.getByTestId('demo-panel').getByRole('button', { name: 'Отклонить' }).click();

    await switchTo(page, TRAINEE);
    await expect(page.getByTestId('decision-badge')).toHaveText('Отклонена');
    await expect(page.getByTestId('return-to-task')).toHaveCount(0);
    await expect(page.getByText('Склонируйте репозиторий todo-service')).toHaveCount(0);
    await expect(page.getByText('Следующий шаг по задаче')).toHaveCount(0);
  });

  test('уже имеющийся доступ: агент не предлагает заявку', async ({ page }) => {
    await cleanSession(page);
    await loginAs(page, OPERATOR);
    await page.getByTestId('demo-panel').getByRole('button', { name: 'Право без заявки' }).click();

    await switchTo(page, TRAINEE);
    await expect(page.getByTestId('access-badge')).toContainText('Доступ подтверждён');
    await ask(page, 'Не могу начать первую задачу. Что делать?');
    await expect(page.getByText(/Доступ уже подтверждён сервером/)).toBeVisible();
    await expect(page.getByTestId('proposal-PRP-77')).toHaveCount(0);
  });

  test('долгий ответ: ожидание видно, интерфейс не блокируется', async ({ page }) => {
    await page.goto('/?latency=1500');
    await page.evaluate(() => window.localStorage.clear());
    await page.reload();

    await loginAs(page, TRAINEE);
    await ask(page, 'Не могу начать первую задачу. Что делать?');
    await expect(page.getByTestId('assistant-thinking')).toBeVisible();
    await expect(page.getByText('Настроить CI для учебного сервиса')).toBeVisible();
    await expect(page.getByText(/Уточню, чтобы помочь точно/)).toBeVisible({ timeout: 8000 });
    await expect(page.getByTestId('assistant-thinking')).toHaveCount(0);
  });

  test('простое локальное действие реагирует быстрее 1 с', async ({ page }) => {
    await cleanSession(page);
    await loginAs(page, OPERATOR);
    await page.getByTestId('demo-panel').getByRole('button', { name: 'Право без заявки' }).click();

    await switchTo(page, TRAINEE);
    const started = Date.now();
    await expect(page.getByTestId('access-badge')).toContainText('Доступ подтверждён');
    const elapsed = Date.now() - started;
    expect(elapsed).toBeLessThan(1000);
  });
});
