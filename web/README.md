# web/ — клиент AI-buddy «Первый PR»

React + TypeScript (Vite). Все обращения к серверу вынесены в один клиент `src/api/`:

- `types.ts` — контрактные типы (соответствуют будущему `contracts/openapi.yaml`);
- `client.ts` — `HttpApiClient` (настоящий сервер) + хранение тестовой сессии;
- `testAdapter.ts` — `TestApiClient`, тестовый адаптер с тем же контрактом (фикстуры `fixtures.ts` повторяют будущие `contracts/examples/`);
- `index.ts` — `createClient()` выбирает адаптер по переменной окружения.

## Запуск

```bash
cd web
npm install
npm run dev
```

По умолчанию `VITE_API_MODE=test`: экран строится из контрактных фикстур, сервер не нужен.

Тесты: `npm test` · Сборка: `npm run build`.

## Переключение на настоящий сервер

1. Создайте `web/.env` (или скопируйте `.env.example`):

```
VITE_API_MODE=http
VITE_API_BASE_URL=/api
VITE_PROXY_TARGET=http://127.0.0.1:8000
```

2. Перезапустите `npm run dev`. Dev-сервер Vite проксирует `/api/*` на Flask (`VITE_PROXY_TARGET`).
3. Ожидаемые маршруты: `POST /api/session`, `DELETE /api/session`, `GET /api/workspace`, `POST /api/messages`, `POST /api/proposals/{id}/confirm` — тело и поля по `contracts/openapi.yaml` (пока не опубликован, типы в `src/api/types.ts` являются рабочим черновиком контракта для сверки с B1).

## Тестовые учётные записи (фикстуры)

- `trainee-vasya` — стажёр, задача `TSK-101`, доступ к `git.avito.local/trainee/todo-service` отсутствует;
- `demo-operator` — демооператор (пустой workspace, без чужих заявок).

Роль пользователя из браузера не передаётся как полномочие: сессия выдаётся сервером, права проверяет сервер.
