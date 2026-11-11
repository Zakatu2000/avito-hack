# Spec 006 · Имитация сервисов (MSW + localStorage)

## Слой
- Фронтенд ходит только через типизированный API-клиент `apiFetch` (zod-схемы ответов) → `services/index.ts` (интерфейс `BuddyService`: `getChecklist`, `createLeaveRequest`, `requestAccess`, `approveRequest`, `listRequests` и др.) → TanStack Query-хуки.
- MSW перехватывает `/api/*` в браузере (service worker) и в тестах (`msw/node`).
- Состояние (запросы + прогресс чек-листов) хранится в `localStorage` под ключом `ai-buddy-db-v1` и переживает перезагрузку страницы.

## Имитация сети
- Задержка каждого запроса: 300–1200 мс (случайно), переопределяется в dev-панели (300 мс / 1000 мс / авто).
- Сбои: режимы «выкл / всегда / 50%» в dev-панели → HTTP 500 c кодом `SIMULATED_FAILURE`, чтобы отрабатывать состояния loading/error и повторы.
- Без задержек и сбоев оставлены `GET /api/users` и `GET /api/me` — вход должен работать всегда.

## Замена на реальные сервисы
1. Поднять бэкенд с совместимыми контрактами (zod-схемы = контракт ответов).
2. Установить `VITE_API_URL=https://api.example.com` и `VITE_ENABLE_MSW=false` в `.env`.
3. UI, хуки и тесты не меняются: клиент строит URL из `VITE_API_URL`.

## Критерии приёмки
- [x] Действие считается выполненным, когда мок-сервис вернул результат, UI его показал и сохранил (localStorage).
- [x] Состояния загрузки (Skeleton, спиннеры кнопок) и ошибки (ErrorState, toast + повтор) воспроизводятся предсказуемо через dev-панель.
- [x] «Сбросить демо-данные» в dev-панели возвращает БД к сиду.

Ссылки в коде: `src/mocks/` (`handlers.ts`, `db.ts`, `simulate.ts`), `src/api/client.ts`, `src/components/DevPanel.tsx`.
