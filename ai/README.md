# AI-контур AI-buddy «Первый PR» (Hack&Change 2026)

Пакет агента для backend-сервера команды (Flask + PostgreSQL). Контракт —
**командный, уже зафиксирован**: `contracts/agent.md` v1.0.0 и
`contracts/openapi.yaml` v1.3.0 (владелец — Web 2, задача B1). AI-зона
зеркалит контракт типами и не создаёт параллельных несовместимых схем.

## Граница ответственности

AI **не делает** и не может: выдавать/отзывать права; создавать/подтверждать
заявки; генерировать `proposalId`/`requestId`/статусы; менять
`requestStatus`/`effectiveAccess`; подключаться к PostgreSQL; принимать
browser cookies; читать произвольные ресурсы; считать ответ LLM
доказательством фактического действия. AI читает факты через разрешённые
read-only инструменты и возвращает типизированное решение; запись и проверка
подтверждения принадлежат серверу.

## Интеграция (in-process, основной путь)

Сервер вызывает агента синхронно в пуле потоков `AgentRunner` (семафор 4,
валидация решения), см. `server/dialog.py`:

```python
# contracts/agent.md v1.0.0
Agent.respond(text: str, tools: ScopedReadTools) -> {"kind", "text", "sourceId", "aiMode"}
```

Подключение (Web 2, B4): сервер подхватывает фабрику из переменной
`BUDDY_AGENT_FACTORY` (import string, вызывается без аргументов):

```text
BUDDY_AGENT_FACTORY=agent.factory:create_agent
```

**Правило согласованности режима:** сервер считает режим `live`, если фабрика
задана, иначе `demo`, и отклоняет решение с несовпадающим `aiMode`. Поэтому
`BUDDY_AGENT_FACTORY` задаём только вместе с `AI_MODE=live`; демо —
это отсутствие фабрики (server-side `DemoAgent`), либо локальный запуск этого
пакета. Скрытая подмена режима исключена валидацией на стороне сервера.

**Онбординг-чат (`/api/buddy/chat`)** в live-режиме использует тот же
провайдер через `agent.factory:create_provider`: детерминированный роутер
(`server/orchestrator.py`) по-прежнему владеет фактами, источниками, интентом
из закрытого набора и всеми записями (preview действий, разбор ответа
куратора); LLM только формулирует текст read-only ответа и может
перенаправить интент только внутри read-only `STEERABLE` (`mentor` и любые
побочные эффекты выбирает исключительно детерминированный серверный роутер).
`unsafe`, неизвестные факты (abstain) и `curator_reply` к провайдеру не
отправляются. Если retrieval нашёл источники, ответ принимается только с
непустым `sourceIds`, каждый из которых принадлежит найденным `chunkId`;
чужой/смешанный ID, отсутствующая цитата, неизвестный ID или число в тексте,
утверждение о выполненном действии → детерминированный фолбэк. Сервер
проверяет актуальность сессии и фактов после ответа модели; изменившееся
состояние возвращает 409, а не ответ по устаревшим данным. Вызов провайдера
происходит без открытого соединения с БД, ограничен семафором
`BUDDY_LLM_SLOTS` (по умолчанию 4) и ожиданием `BUDDY_LLM_WAIT` (8 секунд).
Невалидный JSON или `finish_reason != stop` → детерминированный фолбэк;
сбой провайдера/перегрузка → 503 `unavailable`, без подмены live-режима
демоответом. Live без полного AI_* конфига при заданной фабрике — ошибка
старта сервера.

Инструменты чтения (строит сервер, без userId, скоуп — текущее назначение):
`current_task()`, `instruction()`, `effective_access()` → `missing|granted|unknown`,
`current_request()`. Скрытый и отсутствующий объект читаются одинаково пусто;
ошибка чтения права — `unknown`, а не «права нет».

## Структура

| Путь | Назначение | Задача |
|---|---|---|
| `ai/context/models.py` | Типы контракта: `Workspace`, `Task`, `Source`, `Ticket`, `AgentDecision` | A0.1 |
| `ai/context/tools.py` | `ScopedReadTools`, `WorkspaceTools`, адаптер `wrap_tools` | A0.1 → A2 |
| `ai/agent/base.py` | Порт `Agent.respond` (sync) | A0.1 → A3 |
| `ai/agent/policy.py` | Детерминированная policy S01–S12 + `BuddyAgent` (LLM-перефразирование) | A3 |
| `ai/agent/factory.py` | Фабрика `create_agent` для `BUDDY_AGENT_FACTORY` | A4 |
| `ai/providers/` | `LLMProvider` (sync), `DeepSeekProvider` — OpenAI-совместимый адаптер | A0 → A4 |
| `ai/server.py` | Опциональный HTTP-адаптер (`/health`, `/internal/ai/respond`) | A0.1 |
| `ai/tests/` | unit/контрактные тесты; `test_contract_examples.py` валидирует `contracts/examples/*.json` | A0.1+ |
| `ai/evals/` | офлайн- и live-диалоги (40 + 18) и runner | A5 |
| `docs/sdd/` | SDD: `sources.md`, `cases.md`, `agent.md` | A1 |

## Быстрый старт (Windows, из корня репозитория)

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e "ai[dev]"
cd ai
..\.venv\Scripts\python -m pytest --cov --cov-report=term-missing   # тесты + покрытие (цель >= 90%)
..\.venv\Scripts\python -m uvicorn server:app --reload --port 8100  # опциональный HTTP-адаптер
```

Проверка: `curl http://127.0.0.1:8100/health` → `{"status":"ok"}`.
`/health` ничего не раскрывает о конфигурации; публичные `/docs` отключены.

## Режимы и переменные окружения

Шаблон — `ai/.env.example` (копировать в `ai/.env`, в git не коммитить).
Для Docker-сборки переменные перечислены в `compose.yaml`.

| Переменная | Значение |
|---|---|
| `AI_MODE` | `demo` (по умолчанию; без ключа; воспроизводимо) / `live` |
| `AI_PROVIDER` | `openai_compatible` / `demo` (устаревшее `deepseek` принимается) |
| `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY`, `AI_TIMEOUT_SECONDS` | любой OpenAI-совместимый chat-completions endpoint; обязательны только для `live`. Алиасы `DEEPSEEK_BASE_URL`/`DEEPSEEK_MODEL`/`DEEPSEEK_API_KEY`/`DEEPSEEK_TIMEOUT_SECONDS` поддерживаются |
| `BUDDY_AGENT_FACTORY` | import string фабрики агента; задавать только вместе с `AI_MODE=live` |
| `BUDDY_AGENT_TIMEOUT` | бюджет `AgentRunner` в секундах; должен превышать `AI_TIMEOUT_SECONDS` |

Инварианты: `live` без полного конфига — ошибка при старте, не скрытый
fallback; сбой провайдера — исключение, которое сервер превращает в 503
(`unavailable`), без ложного успеха. Ключи не коммитим и не логируем.
Тайм-аут провайдера строго меньше бюджета раннера — иначе сервер отклонит
конфигурацию при старте.

## Текущий статус

A0–A6 выполнены: типы контракта, read-only инструменты, детерминированная
policy S01–S12 (`BuddyAgent`), OpenAI-совместимый провайдер (`DeepSeekProvider`:
json_object, один retry на пустой ответ, fail-fast по 429/5xx/timeout),
фабрики `create_agent`/`create_provider`, опциональный HTTP-адаптер. Offline
evals включают 40 legacy-диалогов, 24 кейса onboarding-router и 13 проверок
server-side LLM output gate: **77/77** (2026-11-14, без сети и ключа).
Отдельный live-набор из 18 legacy-диалогов ранее прошёл 58/58 с реальным
провайдером (`python -m evals.runner --live`, нужен ключ; 2026-11-11).
**Живой вызов проверен 2026-11-10**: ровно 3 синтетических smoke-запроса к
DeepSeek (`deepseek-chat`, api.deepseek.com) через `create_agent` — 3/3
решения корректны и выведены из фактов сервера; формулировка без ключевых
слов («я застрял с первой штукой») в live дала `propose_access` (intent
распознан), `approved` без права — `answer` без призыва начинать, запрос
чужого админ-доступа не расширил полномочия. Время: 1,33–2,15 с на запрос.
Полный live-eval на произвольных формулировках не выполнялся — точность
требует пилота. Ключ передан через env, в репозитории отсутствует.

## Handoff

- **B4**: фабрика агента и примечания по режимам — выше; контрактные примеры
  валидируются тестом `ai/tests/test_contract_examples.py`.
- **F3**: тексты и виды решений (`kind`) — после A3.
- **B6**: команды запуска/тестов/покрытия выше; покрытие ai/ считается
  отдельно от server/ и суммируется без двойного учёта.
