"""Read-only guidance for the portal, with optional grounded wording."""
import re
import secrets

from ai.buddy_intents import classify
from server import knowledge, onboarding, orchestrator
from server import portal_adaptation as adaptation
from server.portal_auth import current_account

# Smalltalk that must never reach the KB fallback: a bare greeting is not an
# explain-query, so answer it adaptively with the real onboarding context.
_GREETING_RE = re.compile(
    r"^(привет(ствую)?|здравствуй(те)?|добрый\s+(день|вечер)|доброе\s+утро|"
    r"хай|hello|hi|hey|ку|салют)[\s!.…]*$",
    re.IGNORECASE)
_IDENTITY_RE = re.compile(
    r"^(?:(?:привет|здравствуй(?:те)?)[,\s]*)?"
    r"(?:ты кто|кто ты(?: такой| такая)?|что ты умеешь|чем ты можешь помочь)"
    r"[\s?!.…]*$",
    re.IGNORECASE)
_THANKS_RE = re.compile(r"^(спасибо|благодарю|thanks|thank you)[\s!.…]*$", re.IGNORECASE)
_CORRECTION_RE = re.compile(
    r"\b(?:это не (?:онбординг|то)|не про онбординг|не по теме|не о том|"
    r"я не это спрашивал[а]?|ты не понял[а]?|ответ не туда)\b",
    re.IGNORECASE)
_TASK_HELP_RE = re.compile(
    r"\b(?:решить|разобрать|сделать|выполнить)\b.{0,35}\bзадач\w*"
    r"|\bзадач\w*.{0,35}\b(?:решить|разобрать|сделать|выполнить)\b",
    re.IGNORECASE)
_DOCS_LOCATION_RE = re.compile(
    r"\b(?:где|куда|как найти|найти)\b.{0,40}"
    r"\b(?:документ\w*|инструкц\w*|мануал\w*|баз\w+\s+знан\w*)",
    re.IGNORECASE)
_WELLBEING_MARKERS = (
    "устал", "устала", "устали", "нет сил", "тяжело работать", "перегружен",
    "перегружена", "выгор", "надоело работать",
)

_EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")


def _redact_contacts(text):
    return _PHONE_RE.sub("[номер скрыт]", _EMAIL_RE.sub("[email скрыт]", text))


def _query_summary(text):
    """Echo a short, non-identifying topic in an abstention, not the full prompt."""
    summary = _redact_contacts(text)
    return " ".join(summary.split())[:100].strip(" «»")



_MESSAGE_ID = re.compile(r"[A-Za-z0-9._-]{8,80}")


def valid_message_id(value):
    return isinstance(value, str) and _MESSAGE_ID.fullmatch(value) is not None


def _action(target, label):
    return dict(id=target, kind="navigate", target=target, label=label)


def _route(conn, account, text, task_id, facts, legacy_items):
    intent = classify(text)
    lowered = text.casefold()
    step = facts["nextStep"]
    selected = next((i for i in facts["items"] if i["id"] == task_id), None)
    related = (selected or step or {}).get("id")
    related_query = {"task": related} if related else {}
    timeline = _action("/timeline", "Открыть путь адаптации")
    contacts = _action("/contacts", "Контакты наставника")
    support = _action(adaptation.url("/requests/new/technical_support", **related_query),
                      "Создать техническое обращение")
    kb = _action(adaptation.url("/kb", q=text[:200]), "Открыть базу знаний")
    if intent == "unsafe":
        return intent, "Не передавайте пароли и токены. Права и действия проверяет сервер.", [timeline], []
    if _GREETING_RE.match(text) or _IDENTITY_RE.match(text):
        first_name = account["name"].split()[0]
        context = f' Следующий шаг по плану: «{step["title"]}».' if step else ""
        return "greeting", f"Привет, {first_name}! Я AI-buddy: помогу с доступами, заявками, обучением и адаптацией.{context}", [], []
    if _THANKS_RE.match(text):
        return "greeting", "Всегда пожалуйста! Если появится вопрос по адаптации, напиши.", [], []
    if _CORRECTION_RE.search(text):
        return "feedback", "Понял, предыдущий ответ был не по теме. Уточни, что именно ты хотел узнать.", [], []
    if _TASK_HELP_RE.search(text) and not selected:
        return "feedback", "Пришли формулировку задачи, ожидаемый результат и расскажи, где застрял.", [timeline], []
    if _DOCS_LOCATION_RE.search(text) and not selected:
        return "documents", "Документы и инструкции собраны в Базе знаний. Напиши название или тему, чтобы сузить поиск.", [_action("/kb", "Открыть базу знаний")], []
    if "отгул" in lowered or "отпуск" in lowered:
        return "leave", "Укажите даты и причину в форме отгула.", [_action("/requests/new/leave", "Оформить отгул")], []
    if any(word in lowered for word in ("почему я не могу продолжить", "что мешает", "блокиру")) or selected:
        blockers = selected["blockers"] if selected else facts["blockers"]
        if blockers:
            return "next_step", " ".join(b["reason"] + "." for b in blockers[:3]), [
                _action(b["action"], "Устранить блокировку") for b in blockers[:3]
            ], []
        if selected:
            return "next_step", f'{selected["title"]}. {selected["nextStep"]}', [timeline], []
    if intent == "access":
        systems = {"репозитор": "repo", "jira": "jira", "confluence": "confluence", "grafana": "grafana"}
        system = next((key for word, key in systems.items() if word in lowered), None)
        if system and system in adaptation.effective_grants(conn, account["user_id"]):
            return intent, "Действующий демо-доступ подтверждён. Если система не открывается, опишите ошибку.", [support], []
        params = {**related_query, **({"system": system} if system else {})}
        return intent, "Выберите систему, срок и обоснование. Отправка требует подтверждения.", [
            _action(adaptation.url("/requests/new/access", **params), "Запросить доступ")
        ], []
    if "наставник" in lowered and any(word in lowered for word in ("обсуд", "консультац", "встреч", "созвон")):
        return "mentor", "Укажите тему и удобное время. Наставник увидит запрос в демоочереди.", [
            _action(adaptation.url("/requests/new/mentor_consultation", **related_query), "Запросить консультацию")
        ], []
    if intent == "progress":
        quick = facts["quickStart"]
        return intent, f"Быстрый старт: {sum(group['done'] for group in quick)} из {len(quick)} шагов.", [timeline], []
    if intent == "next_step" or "что мне делать" in lowered:
        open_item = next((item for item in legacy_items if item["status"] in ("in_progress", "pending_approval")), None)
        if open_item and any(marker in lowered for marker in ("другую задачу", "новую задачу", "переключиться на")):
            return "next_step", f'Ты хочешь перейти к другой задаче. Сначала уточни с наставником, что мешает завершить «{open_item["title"]}».', [timeline], []
        if step:
            return "next_step", "Следующий шаг: " + step["title"], [timeline], []
        blockers = facts["blockers"]
        text = blockers[0]["reason"] if blockers else "На текущем этапе нет новых шагов."
        return "next_step", text, [_action(blockers[0]["action"], "Устранить блокировку")] if blockers else [timeline], []
    if intent in ("mentor", "feedback", "curator_reply"):
        if any(marker in lowered for marker in _WELLBEING_MARKERS):
            return intent, "Сочувствую, похоже, ты сильно устал. Обсуди нагрузку с наставником или руководителем.", [contacts], []
        return intent, "Опишите задачу, что уже попробовали и где нужна помощь.", [contacts], []
    if intent == "troubleshoot" and ("скач" in lowered or "файл" in lowered):
        return intent, "Понял: файл не скачивается. Напиши, в какой системе он находится, точный текст ошибки и что происходит после нажатия.", [support, contacts], []
    safe_text = _query_summary(text)
    sources = knowledge.search(conn.cursor(), text, track=facts["track"], role=account["role"], limit=3,
                               min_rank=knowledge.MIN_RELEVANCE_SCORE if intent == "explain" else 0)
    answer = (sources[0]["snippet"] + "\nИсточник: " + sources[0]["title"]) if sources else f"По запросу «{safe_text}» в базе адаптации нет проверенного ответа. Уточни шаг или систему, либо обратись к наставнику."
    actions = [kb]
    if intent == "troubleshoot":
        actions.append(support)
    if intent == "learn" or "где изучить" in lowered:
        actions.append(_action(adaptation.url("/requests/new/learning_request", topic=text[:200], **related_query), "Запросить материал"))
    if not sources and len(actions) == 1:
        actions.append(contacts)
    return intent, answer, actions, sources


def _prepare(conn, account, text, task_id, read_plan, read_checklist, error):
    facts = read_plan(conn, account)
    if task_id and not any(item["id"] == task_id for item in facts["items"]):
        raise error(404, "Пункт адаптации не найден", "NOT_FOUND")
    result = _route(conn, account, text, task_id, facts, read_checklist(conn, account["user_id"]))
    return result, facts


def respond(connect, account, text, task_id, history, read_plan, read_checklist,
            llm, slots, wait, error):
    user_id = account["user_id"]
    with connect() as conn:
        reply, facts = _prepare(conn, account, text, task_id, read_plan, read_checklist, error)
        profile = onboarding.read_profile(conn.cursor(), user_id)
    intent, answer, actions, sources = reply
    method = "rules"
    grounded = bool(sources) and intent in orchestrator.STEERABLE
    free_form = intent == "explain" and not sources
    if llm is not None and profile and (grounded or free_form):
        quick = facts["quickStart"]
        done = sum(group["done"] for group in quick)
        payload = dict(intent=intent, text=answer, sources=sources, nextStep=None,
                       progress=dict(completed=done, total=len(quick),
                                     pct=round(done / len(quick) * 100) if quick else 0))
        safe_history = [
            dict(role=turn["role"], text=_redact_contacts(turn["text"])) for turn in history
        ]
        llm_request = orchestrator._build_llm_request(
            _redact_contacts(text), payload, profile, history=safe_history,
        )
        if not slots.acquire(timeout=wait):
            raise error(503, "Помощник перегружен. Повторите позже", "UNAVAILABLE")
        try:
            response = orchestrator.call_provider(llm, llm_request)
        except orchestrator.BuddyProviderUnavailable:
            raise error(503, "Помощник временно недоступен", "UNAVAILABLE") from None
        finally:
            slots.release()
        with connect() as conn:
            fresh = current_account(conn)
            if fresh is None or fresh["user_id"] != user_id:
                raise error(401, "Войдите в аккаунт", "UNAUTHENTICATED")
            fresh_reply, fresh_facts = _prepare(conn, fresh, text, task_id, read_plan, read_checklist, error)
            fresh_profile = onboarding.read_profile(conn.cursor(), user_id)
            if fresh_profile != profile or fresh_reply != reply or fresh_facts != facts:
                raise error(409, "Состояние изменилось. Повторите запрос.", "CONFLICT")
        parsed = orchestrator._parse_llm_output(response.content) if response.finish_reason == "stop" else None
        if parsed:
            target, candidate, source_ids = parsed
            # The router can clarify free text but cannot override a structured
            # adaptation flow or supply actions. Links come from server rules.
            allowed = target == intent or (free_form and target in ("off_topic", "feedback", "prepare"))
            valid, cited = orchestrator._validated_source_citations(payload, source_ids)
            if (allowed and valid and orchestrator._text_consistent_with_facts(candidate, payload)
                    and not re.search(r"https?://|\]\(", candidate, flags=re.IGNORECASE)):
                intent, answer, sources, method = target, candidate, cited, "model"
                if target == "off_topic":
                    actions = []
    return dict(intentId=intent, text=answer,
                actions=list({action["id"]: action for action in actions}.values()),
                sources=sources, answerMethod=method)
