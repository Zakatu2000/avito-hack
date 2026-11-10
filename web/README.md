# Веб-клиент AI-buddy «Первый PR»

React + TypeScript. Node 22.12+ или 24+. Публичный серверный контракт расположен в ../contracts/openapi.yaml. Файл src/api/types.ts описывает модели экранов; HttpApiClient преобразует ответы API в эти модели.

По умолчанию используется HTTP API с HttpOnly-cookie. Локальное хранилище содержит только метаданные для восстановления экрана. Сервер проверяет права независимо от этих метаданных.

    npm ci
    npm run dev

Vite проксирует /api и /demo на http://127.0.0.1:5050. При необходимости задайте VITE_PROXY_TARGET. Сервер запускается по README в корне репозитория. Для общей сборки выполните npm run build; Flask раздаёт web/dist.

Учебные аккаунты HTTP-режима: intern-demo, intern-ready, intern-new, operator-demo. Пароль training-only передаётся клиентом для этого учебного входа. Полноценную корпоративную авторизацию подключает серверная интеграция.

    npm test
    npm run test:coverage
    npm run build

Для отдельного режима фронтенд-фикстур выполните VITE_API_MODE=test npm run dev. В нём доступны прежние trainee-vasya и demo-operator. Скрипты capture-screens.mjs и record-demo-video.mjs относятся к этой сборке и ожидают стенд в таком режиме.

Для проверки настоящего API на отдельной демобазе с исходным состоянием:

    BUDDY_LIVE_URL=http://127.0.0.1:5050 npx playwright test --config playwright.live.config.ts

Нужен Chrome. Сервер должен иметь BUDDY_DEMO_OPERATOR=1. Тест проверяет две отдельные сессии и изменяет демоданные до выдачи доступа. Повторный запуск требует штатного сброса выделенной демобазы.
