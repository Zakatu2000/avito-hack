# AI-контур AI-buddy «Первый PR» (Hack&Change 2026)

Изолированный stateless Python-сервис агента. Вызывается **только** backend-сервером
через `POST /internal/ai/respond` с доверенным `AgentContext`.

## Граница ответственности

AI **не делает** и не может: выдавать/отзывать права; создавать/подтверждать заявки;
менять `requestStatus`/`effectiveAccess`; подключаться к PostgreSQL; принимать
browser cookies; читать произвольные ресурсы; считать ответ LLM доказательством
фактического действия. AI читает доверенные факты и формирует типизированный
`AgentResult`; запись и проверка подтверждения принадлежат серверу.

## Структура

| Путь | Назначение | Задача |
|---|---|---|
| `ai/context/models.py` | Pydantic-модели входа/выхода (временный контракт) | A0 → A2 |
| `ai/agent/base.py` | Порт `Agent.respond` | A0 → A3 |
| `ai/providers/` | `LLMProvider`, `DemoProvider`, `DeepSeekProvider` | A0 → A4 |
| `ai/server.py` | FastAPI-адаптер, `/health`, `/internal/ai/respond` | A0 |
| `ai/tests/` | unit/контрактные тесты (LLM всегда замокан) | A0+ |
| `ai/evals/` | офлайн-диалоги и runner | A5 |
| `docs/sdd/` | SDD: `sources.md`, `cases.md`, `agent.md` | A1 |

> **Временная типизированная фикстура.** Каталога `contracts/` ещё нет (это задача
> B1 команды). До его появления единственный источник типов — `ai/context/models.py`
> (camelCase, помечен как PROVISIONAL). Параллельный контракт не создаём; после
> публикации B1 имена полей сверяются и правятся здесь.

## Быстрый старт (Windows, из корня репозитория)

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e "ai[dev]"
cd ai
..\.venv\Scripts\python -m pytest --cov --cov-report=term-missing   # тесты + покрытие (цель >= 90%)
..\.venv\Scripts\python -m uvicorn server:app --reload --port 8100  # локальный запуск
```

Проверка: `curl http://127.0.0.1:8100/health` → `{"status":"ok"}`.
`/health` ничего не раскрывает о конфигурации; публичные `/docs` отключены.

## Режимы и переменные окружения

Шаблон — `ai/.env.example` (копировать в `ai/.env`, в git не коммитить).

| Переменная | Значение |
|---|---|
| `AI_MODE` | `demo` (по умолчанию; без ключа; воспроизводимо; `aiMode=demo`) / `live` |
| `AI_PROVIDER` | `deepseek` / `demo` |
| `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `DEEPSEEK_API_KEY`, `DEEPSEEK_TIMEOUT_SECONDS` | обязательны только для `live` |

Инварианты режимов: `live` без полного конфига — ошибка при старте, а не скрытый
fallback; сбой провайдера — явное `provider_unavailable`, без ложного успеха.
Ключи не коммитим и не логируем.

## Текущий статус (после A0)

Сервис возвращает типизированную заглушку `errorCode=agent_not_implemented` —
это честный маркер, а не фальшивый успех. Бизнес-логика появляется в A2–A4.

## Handoff

- **B4**: порт и схема обмена — `POST /internal/ai/respond`, запрос
  `AgentRespondRequest {context, userMessage}`, ответ `AgentResult` (camelCase);
  примеры — `ai/tests/conftest.py::base_context_payload`.
- **F3**: тексты и типы действий (`actionType`) — после A3.
- **B6**: команды запуска/тестов/покрытия выше; AI-сервис запускается отдельно
  от backend, режим по умолчанию — `demo`.
