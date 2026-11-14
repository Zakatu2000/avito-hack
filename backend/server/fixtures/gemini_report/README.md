# Мультимодальный fixture-pack: отчёт Gemini

Источник: `Проектирование AI-Buddy для стажёров Авито.docx` (исследовательский
отчёт Gemini, 11.11.2026). Пакет фиксирует всё извлечённое из DOCX содержимое,
чтобы демо и тесты работали без внешних сервисов и без vision API.

## Состав

| Файл | Назначение |
| --- | --- |
| `source.docx` | Оригинальный DOCX (sha256 зафиксирован в `images/manifest.json`) |
| `extracted_text.txt` | Полный извлечённый текст: заголовки, абзацы, все таблицы (каталог CHK-01..30, 12 интентов, контракт фронтенда, 32 eval-кейса, демо-сценарий) |
| `images/image6.png` | Архитектурная диаграмма (rId9): Guardrail → Orchestrator → RAG → Executor с HITL-шлюзом → Mock Sandbox |
| `images/image9.png` | Инфографика структуры адаптации (rId6): параметры программы, индекс автономности E1→E2, распределение 30 пунктов и доля HITL |
| `images/image7.png` | Инфографика покрытия (rId12): 32 eval-кейса по 9 категориям и индекс зрелости стека |
| `images/manifest.json` | sha256, размеры, relationship-ID и alt-text каждого изображения |
| `competency_schema.json` | JSON-схема результата competency assessment («Колесо компетенций») |

## Доступность источников

- PDF-курс по ООП на C#, на который ссылается отчёт, **локально недоступен**
  (`unavailable`): модули курса реконструированы строго по таблице CHK-16..23
  самого отчёта и помечены `sourceStatus: reconstructed` в
  `server/fixtures/knowledge_base.json`. Их содержимое не выдумано извне.
- Локальный PDF `Авито_кейс.pdf` — это кейс хакатона (критерии и ограничения),
  он сохранён в `server/fixtures/sources/hackathon_case.pdf`.

## Fallback без vision API

Экран «Колесо компетенций» (`/api/buddy/competency/*`) использует эти файлы как
evidence-вложения: подписи осей и оценки вводятся вручную по схеме
`competency_schema.json`; изображения показываются как эталонные материалы с
alt-text из манифеста. Тест `server/tests/test_competency.py` проходит весь
workflow без какого-либо vision API.
