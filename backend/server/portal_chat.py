"""Read-only guidance for the portal, with optional grounded wording."""
import re
import secrets

from ai.buddy_intents import classify
from server import knowledge, onboarding, orchestrator
from server import portal_adaptation as adaptation
from server.portal_auth import current_account

_MESSAGE_ID = re.compile(r"[A-Za-z0-9._-]{8,80}")


def valid_message_id(value):
    return isinstance(value, str) and _MESSAGE_ID.fullmatch(value) is not None


def _action(target, label):
    return dict(id=target, kind="navigate", target=target, label=label)


def _route(conn, account, text, task_id, facts):
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
        if step:
            return "next_step", "Следующий шаг: " + step["title"], [timeline], []
        blockers = facts["blockers"]
        text = blockers[0]["reason"] if blockers else "На текущем этапе нет новых шагов."
        return "next_step", text, [_action(blockers[0]["action"], "Устранить блокировку")] if blockers else [timeline], []
    if intent in ("mentor", "feedback", "curator_reply"):
        return intent, "Опишите задачу, что уже попробовали и где нужна помощь.", [contacts], []
    sources = knowledge.search(conn.cursor(), text, track=facts["track"], role=account["role"], limit=3)
    answer = (sources[0]["snippet"] + "\nИсточник: " + sources[0]["title"]) if sources else "В доступной базе нет подходящей инструкции."
    actions = [kb]
    if intent == "troubleshoot":
        actions.append(support)
    if intent == "learn" or "где изучить" in lowered:
        actions.append(_action(adaptation.url("/requests/new/learning_request", topic=text[:200], **related_query), "Запросить материал"))
    if not sources and len(actions) == 1:
        actions.append(contacts)
    return intent, answer, actions, sources


def _prepare(conn, account, text, task_id, read_plan):
    facts = read_plan(conn, account)
    result = _route(conn, account, text, task_id, facts)
    return result, facts


def respond(connect, account, data, read_plan, ai_mode, llm, slots, wait, error):
    text = data.get("message")
    task_id = data.get("taskId")
    message_id = data.get("messageId")
    if (not set(data) <= {"message", "taskId", "messageId"} or not isinstance(text, str)
            or not 1 <= len(text.strip()) <= 4000 or "\x00" in text
            or (task_id is not None and (not isinstance(task_id, str) or len(task_id) > 64))
            or (message_id is not None and not valid_message_id(message_id))):
        raise error(400, "Проверьте сообщение")
    text = text.strip()
    user_id = account["user_id"]
    with connect() as conn:
        reply, facts = _prepare(conn, account, text, task_id, read_plan)
        if task_id and not any(item["id"] == task_id for item in facts["items"]):
            raise error(404, "Пункт адаптации не найден", "NOT_FOUND")
        profile = onboarding.read_profile(conn.cursor(), user_id)
    intent, answer, actions, sources = reply
    method = "rules"
    if llm is not None and sources and profile and intent in orchestrator.STEERABLE:
        quick = facts["quickStart"]
        done = sum(group["done"] for group in quick)
        payload = dict(intent=intent, text=answer, sources=sources, nextStep=None,
                       progress=dict(completed=done, total=len(quick), pct=round(done / len(quick) * 100)))
        safe_text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", text)
        llm_request = orchestrator._build_llm_request(safe_text, payload, profile)
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
            fresh_reply, fresh_facts = _prepare(conn, fresh, text, task_id, read_plan)
            fresh_profile = onboarding.read_profile(conn.cursor(), user_id)
            if fresh_profile != profile or fresh_reply != reply or fresh_facts != facts:
                raise error(409, "Состояние изменилось. Повторите запрос.", "CONFLICT")
        parsed = orchestrator._parse_llm_output(response.content) if response.finish_reason == "stop" else None
        if parsed and parsed[0] == intent and orchestrator._text_consistent_with_facts(parsed[1], payload):
            valid, cited = orchestrator._validated_source_citations(payload, parsed[2])
            if valid and not re.search(r"https?://|\]\(", parsed[1], flags=re.IGNORECASE):
                answer, sources, method = parsed[1], cited, "model"
    # Keep the original reply shape for clients that haven't opted into message IDs.
    result = dict(intentId=intent, text=answer, actions=list({a["id"]: a for a in actions}.values()))
    if message_id is None:
        return result
    with connect() as conn:
        fresh = current_account(conn)
        if fresh is None or fresh["user_id"] != user_id:
            raise error(401, "Войдите в аккаунт", "UNAUTHENTICATED")
        adaptation.log_event(conn, user_id, "chat_answered", message_id)
    return dict(**result, aiMode=ai_mode, answerMethod=method, sources=sources, messageId=message_id)
