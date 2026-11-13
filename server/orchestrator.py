"""Buddy orchestrator: closed-intent routing over server-owned facts.

Design (docs/sdd/agent.md invariants preserved):
- facts come only from server reads (profile, checklist state, KB, tools);
- the router classifies into a CLOSED intent set; no free-form LLM decisions;
- side effects never happen here: intents that need one produce an
  ActionPreview through the typed tool registry (preview -> confirm -> audit);
- unknown facts -> honest abstention with a reference pointer, never invented
  content; prompt-injection patterns -> off_topic_unsafe with no tool calls.

Live mode (llm != None): the LLM only formulates the text of a read-only
answer and may steer the intent inside LLM_TARGETS. Facts, sources, previews
and writes stay with the deterministic routing below; security decisions
(unsafe) and the curator-reply parser never go through the LLM. Provider
failures raise BuddyProviderUnavailable -> the API layer answers 503, never a
hidden demo answer under a live aiMode. Invalid/unfinished LLM output falls
back to the deterministic draft of the same intent.
"""
import json
import re

from ai.buddy_intents import (
    INTENTS,
    INJECTION_RE as _INJECTION,
    _CURATOR_MARKERS,
    _UNKNOWN_PATTERNS,
    classify,
)
from server import actions, knowledge, onboarding


class BuddyProviderUnavailable(Exception):
    """Live LLM provider failed; the API layer turns this into 503."""


# Read-only intents the LLM may formulate/steer. Security decisions (unsafe)
# and the deterministic curator-reply parser (DB write) never reach the LLM.
STEERABLE = ("next_step", "progress", "explain", "learn", "troubleshoot",
             "access", "prepare", "feedback", "competency", "off_topic")
# Steering targets: the read-only set plus mentor (its only side effect is a
# draft ActionPreview the user still has to confirm explicitly).
LLM_TARGETS = STEERABLE + ("mentor",)

_BUDDY_JSON_EXAMPLE = (
    '{"intent": "<' + "|".join(LLM_TARGETS) + '>", "text": "..."}'
)

BUDDY_SYSTEM_POLICY = (
    "Ты - AI-buddy онбординга стажёра Авито. Ответь строго одним JSON-объектом "
    '{"intent": "...", "text": "..."}.\n'
    "intent - категория сообщения стажёра, только из списка: "
    + ", ".join(LLM_TARGETS)
    + ". Расшифровка: next_step - что дальше по чек-листу; progress - вопрос "
    "о прогрессе; explain - объяснить термин или практику; learn - учебный "
    "материал; troubleshoot - техническая проблема; access - вопрос о "
    "доступах; prepare - подготовка к встрече/экватору; feedback - помочь "
    "сформулировать вопрос; mentor - стажёр просит живого человека/наставника "
    "или явно не справляется; competency - колесо компетенций и план "
    "развития; off_topic - тема вне онбординга.\n"
    "text - короткий ответ стажёру (2-5 предложений, по-русски) ТОЛЬКО по "
    "переданным фактам: прогресс, следующие шаги, источники и черновик "
    "ответа. Не выдумывай пункты чек-листа, идентификаторы, статусы и "
    "источники; не утверждай, что какое-либо действие уже выполнено - заявки, "
    "сообщения и напоминания оформляются через превью и подтверждает их сам "
    "стажёр. Если фактов недостаточно - честно скажи об этом и предложи "
    "уточнить у наставника. Черновик (draft) - безопасная эталонная "
    "формулировка: можешь переписать её точнее и дружелюбнее, сохранив смысл."
)

# Identifier families the prototype generates. Any such token in LLM text must
# come from the trusted facts, otherwise the text is rejected.
_ID_TOKEN = re.compile(
    r"\b(?:common|backend|analytics|marketing|req|prop|act|task|repo|xlsx|"
    r"playbook|kb)-[0-9a-z][0-9a-z-]*\b|\b(?:ACC|MSG|CAL)-[0-9A-Za-z-]+")

# Claims of performed side effects the LLM must never make: previews are
# created by the server and confirmed by the user, not by the assistant.
_ACTION_CLAIMS = (
    "я отправил", "уже отправлено", "сообщение отправлено", "заявка создана",
    "заявку отправил", "эскалация ушла", "напоминание создано",
    "встреча создана", "доступ выдан", "пункт отмечен", "я отметил",
    "уже выполнено за вас",
)


def _checklist_ref_payload(decorated):
    if decorated is None:
        return None
    return {
        "id": decorated["id"], "title": decorated["title"],
        "status": decorated["status"], "stage": decorated["stage"],
        "stageLabel": decorated["stageLabel"], "timing": decorated["timing"],
        "actor": decorated["actor"],
    }


def _find_item(decorated, item_id):
    for d in decorated:
        if d["id"] == item_id:
            return d
    return None


def _route(cur, user_id, profile, decorated, progress, next_items, intent,
           text, ai_mode):
    """Deterministic routing: builds the full structured payload for `intent`.

    This is the only place side effects happen (mentor preview, curator-reply
    storage, security audit). The LLM never calls into here directly.
    """
    lowered = text.casefold()

    base = {
        "intent": intent,
        "profile": onboarding.profile_card(profile),
        "progress": progress,
        "nextStep": None,
        "checklistItem": None,
        "sources": [],
        "learning": None,
        "actionPreview": None,
        "abstained": False,
        "handoff": False,
        "mode": ai_mode,
    }

    def with_next(payload):
        if next_items:
            top = next_items[0]
            payload["nextStep"] = {
                "itemId": top["id"], "title": top["title"],
                "status": top["status"], "timing": top["timing"],
                "stageLabel": top["stageLabel"],
            }
        return payload

    if intent == "unsafe":
        actions._audit(cur, user_id, None, "security_block",
                       {"reason": "injection_or_secret"})
        return {
            **base,
            "text": "Я помогаю с онбордингом и обучением в Авито и не могу "
                    "выполнить такой запрос. Если вы случайно вставили токен или "
                    "пароль — удалите его из чата и отзовите в вашем сервисе. "
                    "Вернёмся к чек-листу?",
            "sources": [],
        }

    if intent in ("next_step", "progress"):
        lines = []
        if intent == "progress":
            lines.append(
                f"Прогресс: {progress['completed']} из {progress['total']} пунктов "
                f"({progress['pct']}%).")
        open_now = [d for d in decorated
                    if d["status"] in ("in_progress", "evidence_pending")]
        upcoming = [d for d in next_items if d not in open_now][:2]
        if open_now:
            d = open_now[0]
            lines.append(
                f"Сейчас в работе: «{d['title']}» ({d['stageLabel']}).")
            if d["actor"] in onboarding.HUMAN_ACTORS:
                lines.append("Этот шаг выполняет наставник/куратор — можно мягко "
                             "напомнить ему на 1:1.")
        if upcoming:
            nxt = upcoming[0]
            verb = "Далее по плану" if nxt["timing"] != "overdue" else "Просрочено"
            lines.append(f"{verb}: «{nxt['title']}» ({nxt['stageLabel']}).")
        if not lines:
            lines.append("По вашему треку всё закрыто — сверьтесь с наставником, "
                         "что брать дальше.")
        sources = knowledge.search(cur, text, track=profile["track"], limit=2)
        payload = {
            **base,
            "text": " ".join(lines),
            "checklistItem": _checklist_ref_payload(next_items[0]) if next_items else None,
            "sources": sources,
        }
        return with_next(payload)

    if intent == "explain":
        hits, abstained = knowledge.explain_term(cur, text, track=profile["track"])
        if abstained or any(p.search(lowered) for p in _UNKNOWN_PATTERNS):
            hits = [h for h in hits if h["sourceStatus"] != "unavailable"][:1]
            return {
                **base,
                "text": "В одобренной базе знаний этого нет: не буду выдумывать. "
                        "Дам общий ориентир и предложу уточнить у куратора — "
                        "хотите, подготовлю вопрос?",
                "abstained": True,
                "sources": hits,
            }
        top = hits[0]
        ref = top["checklistRefs"][0] if top["checklistRefs"] else None
        linked = _find_item(decorated, ref) if ref else None
        text_out = f"{top['section']}: {top['snippet']}"
        if top["conflictNote"]:
            text_out += f" Важно: {top['conflictNote']}"
        return with_next({
            **base,
            "text": text_out,
            "checklistItem": _checklist_ref_payload(linked),
            "sources": hits,
            "learning": {"kind": "explanation", "topics": top["topics"]},
        })

    if intent == "learn":
        hits = knowledge.search(cur, text, track=profile["track"], limit=3)
        course = [h for h in hits if h["sourceType"] == "educational"] or hits
        if course:
            top = course[0]
            text_out = (f"{top['section']}. {top['snippet']} "
                        f"Спросите себя: что здесь инвариант и как его сломать? "
                        f"Когда будете готовы — покажите пример из своей задачи.")
            return with_next({
                **base,
                "text": text_out,
                "sources": course,
                "learning": {"kind": "lesson", "topics": top["topics"],
                             "socratic": True},
            })
        return with_next({
            **base,
            "text": "По этой теме в базе нет учебного модуля. Предложу пункт "
                    "чек-листа и материалы наставника?",
            "abstained": True,
            "sources": [],
        })

    if intent == "troubleshoot":
        hits = knowledge.search(cur, text, track=profile["track"], limit=2)
        text_out = ("Разберём по шагам: 1) какая именно ошибка и где — пришлите "
                    "текст без токенов и паролей; 2) что менялось перед поломкой; "
                    "3) проверьте по инструкции из источника. Если за 30 минут не "
                    "сдвинется — подготовлю вопрос наставнику.")
        return with_next({**base, "text": text_out, "sources": hits})

    if intent == "access":
        # Bridge to the legacy first-task flow when it applies; otherwise a
        # typed access_request preview is proposed by the API layer.
        task_item = _find_item(decorated, "common-01") or (next_items[0] if next_items else None)
        return with_next({
            **base,
            "text": "Проверю права. Если доступа нет — подготовлю заявку и покажу "
                    "превью перед отправкой: вы всегда подтверждаете действие "
                    "сами, а повторная отправка защищена ключом идемпотентности.",
            "checklistItem": _checklist_ref_payload(task_item),
            "sources": knowledge.search(cur, "доступы чек-лист", track=profile["track"], limit=1),
        })

    if intent == "prepare":
        focus = _find_item(decorated, "common-10") or _find_item(decorated, "common-11")
        hits = knowledge.search(cur, "экваторная встреча 1:1", track=profile["track"], limit=2)
        return with_next({
            **base,
            "text": "Готовимся к встрече: соберу ваш прогресс, доказательства по "
                    "пунктам и вопросы к наставнику. Могу сразу оформить повестку "
                    "и черновик сообщения куратору — через превью.",
            "checklistItem": _checklist_ref_payload(focus),
            "sources": hits,
        })

    if intent == "feedback":
        return with_next({
            **base,
            "text": "Сформулируем так, чтобы на него легко ответить: контекст, "
                    "что уже сделано, конкретный вопрос, желаемый результат. "
                    "Подготовить черновик сообщения наставнику?",
        })

    if intent == "mentor":
        preview, _ = actions.create_preview(
            cur, user_id, "escalation",
            {"severity": "blocker", "to": "mentor",
             "summary": text[:500]},
            checklist_item_id=next_items[0]["id"] if next_items else None)
        return with_next({
            **base,
            "text": "Понимаю, что вопрос важный. Подготовил(а) эскалацию "
                    "наставнику — проверьте текст и подтвердите отправку. "
                    "Срочное/чувствительное лучше продублировать лично.",
            "handoff": True,
            "actionPreview": preview,
        })

    if intent == "curator_reply":
        parsed = parse_curator_reply(cur, user_id, text)
        cur.execute(
            "INSERT INTO curator_messages (user_id, direction, channel, body, parsed) "
            "VALUES (%s, 'in', 'curator', %s, %s)",
            (user_id, text[:4000], json.dumps(parsed["stored"], ensure_ascii=False)))
        lines = [f"Разбор ответа куратора ({len(parsed['actionItems'])} шага):"]
        lines += [f"{i+1}. {a}" for i, a in enumerate(parsed["actionItems"])]
        if parsed["openQuestions"]:
            lines.append("Уточнить: " + "; ".join(parsed["openQuestions"]))
        return with_next({
            **base,
            "text": "\n".join(lines),
            "learning": {"kind": "curator_breakdown",
                         "decision": parsed["decision"],
                         "constraints": parsed["constraints"],
                         "openQuestions": parsed["openQuestions"],
                         "actionItems": parsed["actionItems"]},
            "sources": parsed["sources"],
        })

    if intent == "competency":
        return with_next({
            **base,
            "text": "Откройте экран «Колесо компетенций»: оцените себя по 8 осям "
                    "(0–10), выберите 1–2 зоны развития и составьте план со сроками. "
                    "Смогу отправить план куратору через превью.",
            "learning": {"kind": "competency_hint"},
        })

    return with_next({**base, "text": "Не понял вопрос — уточните, пожалуйста."})


def _known_fact_ids(payload):
    """Identifier tokens the LLM may mention: ids present in the payload."""
    ids = set()
    for key in ("nextStep", "checklistItem"):
        ref = payload.get(key)
        if isinstance(ref, dict):
            for field in ("id", "itemId"):
                value = ref.get(field)
                if isinstance(value, str):
                    ids.add(value.casefold())
    for source in payload.get("sources") or []:
        for field in ("chunkId", "docId"):
            value = source.get(field)
            if isinstance(value, str):
                ids.add(value.casefold())
    return ids


def _text_consistent_with_facts(text, payload):
    """LLM text may only reference ids the trusted facts carry and must not
    claim that any side effect (message/request/reminder) already happened."""
    if not text.strip() or len(text) > 2000:
        return False
    known = _known_fact_ids(payload)
    for token in _ID_TOKEN.findall(text):
        if token.casefold() not in known:
            return False
    lowered = text.casefold()
    return not any(stem in lowered for stem in _ACTION_CLAIMS)


def _parse_llm_output(content):
    """Strict {"intent": str, "text": str} parse; anything else is a fallback."""
    try:
        data = json.loads(content)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    intent, text = data.get("intent"), data.get("text")
    if not isinstance(intent, str) or not isinstance(text, str):
        return None
    if intent not in INTENTS or not text.strip():
        return None
    return intent, text.strip()


def _polish_with_llm(llm, cur, user_id, text, payload, profile,
                     decorated, progress, next_items, ai_mode):
    """Live seam: LLM formulates the text / steers the intent; facts stay local."""
    from providers.base import LLMRequest, ProviderError  # live-only imports

    det_intent = payload["intent"]
    facts = {
        "intent": det_intent,
        "profile": {
            "track": profile["track"],
            "roleCode": profile["role_code"],
            "weekNo": profile["week_no"],
            "stage": onboarding.current_stage_code(profile["week_no"]),
        },
        "progress": progress,
        "nextStep": payload.get("nextStep"),
        "checklistItem": payload.get("checklistItem"),
        "sources": [
            {"title": s["title"], "section": s["section"], "quote": s["quote"]}
            for s in (payload.get("sources") or [])[:3]
        ],
        "draft": payload["text"],
    }
    request = LLMRequest(
        system_policy=BUDDY_SYSTEM_POLICY,
        facts=json.dumps(facts, ensure_ascii=False),
        user_message=text,
        json_example=_BUDDY_JSON_EXAMPLE,
    )
    try:
        response = llm.complete(request)
    except ProviderError as exc:
        raise BuddyProviderUnavailable(str(exc)) from exc
    if response.finish_reason != "stop":
        return payload
    output = _parse_llm_output(response.content)
    if output is None:
        return payload
    llm_intent, llm_text = output
    if llm_intent != det_intent:
        if llm_intent not in LLM_TARGETS:
            return payload
        # Facts were gathered for the deterministic intent: re-route and keep
        # the deterministic text of the new branch, never the LLM text.
        return _route(cur, user_id, profile, decorated, progress, next_items,
                      llm_intent, text, ai_mode)
    if _text_consistent_with_facts(llm_text, payload):
        payload["text"] = llm_text
    return payload


def respond(cur, user_id, text, llm=None, ai_mode="demo"):
    """Build the structured buddy response for one intern message.

    Demo (llm=None) is fully deterministic. In live mode the LLM only touches
    read-only intents; unsafe and curator_reply stay deterministic, and a
    provider failure raises BuddyProviderUnavailable (503 at the API layer).
    """
    profile = onboarding.read_profile(cur, user_id)
    if profile is None:
        return None  # caller maps to 403 (no onboarding profile)
    decorated, progress = onboarding.read_checklist(cur, user_id, profile)
    next_items = onboarding.next_steps(cur, user_id, profile)
    intent = classify(text)
    payload = _route(cur, user_id, profile, decorated, progress, next_items,
                     intent, text, ai_mode)
    if llm is None or intent not in STEERABLE:
        return payload
    return _polish_with_llm(llm, cur, user_id, text, payload, profile,
                            decorated, progress, next_items, ai_mode)


_DECISION_MARKERS = ("ок", "аппрув", "approve", "approved", "соглас", "давай", "принято",
                     "отклон", "reject", "нужно переделать", "поправ")
_CONSTRAINT_MARKERS = ("нельзя", "не пиши", "убери", "без", "запрещ", "обязательно",
                       "только после", "проверь", "do not", "must", "не катим")
_QUESTION_MARKERS = ("?", "уточни", "как думаешь", "когда сможешь", "почему")


def parse_curator_reply(cur, user_id, text):
    """Split a pasted curator answer into decision / constraints / open
    questions / action items. Untrusted text is data, never instructions."""
    lowered = text.casefold()
    if _INJECTION.search(lowered):
        actions._audit(cur, user_id, None, "security_block",
                       {"reason": "indirect_injection", "where": "curator_reply"})
        return {
            "decision": "неразобрано",
            "constraints": [],
            "openQuestions": [],
            "actionItems": ["Текст содержит команды, похожие на инъекцию — "
                            "обрабатываю только человеческую часть ответа."],
            "sources": [],
            "stored": {"decision": "blocked_injection"},
        }
    sentences = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", text) if s.strip()]
    decision = "смотреть детали"
    constraints, questions, items = [], [], []
    for s in sentences[1:] if sentences and any(
            m in sentences[0].casefold() for m in _CURATOR_MARKERS) else sentences:
        low = s.casefold()
        if any(m in low for m in _DECISION_MARKERS) and decision == "смотреть детали":
            decision = "одобрено с замечаниями" if any(
                m in low for m in ("но ", "только", "поправ", "убер")) else "решение есть"
        if any(m in low for m in _CONSTRAINT_MARKERS):
            constraints.append(s)
            items.append(s if s.endswith(".") else s + ".")
        elif "?" in s or any(m in low for m in _QUESTION_MARKERS):
            questions.append(s)
        elif len(s.split()) > 3 and any(v in low for v in (
                "сделай", "проверь", "добавь", "поправь", "убери", "перенеси",
                "оформи", "посмотри", "сверь", "убедись", "напиши", "подготовь")):
            items.append(s if s.endswith(".") else s + ".")
    if not items and not questions:
        items.append("Переспросить куратора: какой следующий шаг он ожидает и к какому сроку.")
    sources = knowledge.search(cur, " ".join(constraints + items)[:300] or text[:300],
                               track=None, limit=2)
    return {
        "decision": decision,
        "constraints": constraints[:5],
        "openQuestions": questions[:5],
        "actionItems": items[:6],
        "sources": sources,
        "stored": {"decision": decision, "constraints": constraints[:5],
                   "openQuestions": questions[:5], "actionItems": items[:6]},
    }
