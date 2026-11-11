"""Buddy orchestrator: closed-intent routing over server-owned facts.

Design (docs/sdd/agent.md invariants preserved):
- facts come only from server reads (profile, checklist state, KB, tools);
- the router classifies into a CLOSED intent set; no free-form LLM decisions;
- side effects never happen here: intents that need one produce an
  ActionPreview through the typed tool registry (preview -> confirm -> audit);
- unknown facts -> honest abstention with a reference pointer, never invented
  content; prompt-injection patterns -> off_topic_unsafe with no tool calls.
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


def respond(cur, user_id, text):
    """Build the structured buddy response for one intern message."""
    profile = onboarding.read_profile(cur, user_id)
    if profile is None:
        return None  # caller maps to 403 (no onboarding profile)
    decorated, progress = onboarding.read_checklist(cur, user_id, profile)
    next_items = onboarding.next_steps(cur, user_id, profile)
    intent = classify(text)
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
        "mode": "demo",
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
