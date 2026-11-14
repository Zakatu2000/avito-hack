"""Pure closed-intent classifier shared by the server router and offline evals.

Keep this module free of server/HTTP imports so the AI evaluation package can
load the production classifier without colliding with its own ``server.py``.
"""
import re

INTENTS = (
    "next_step", "progress", "explain", "learn", "troubleshoot", "access",
    "prepare", "feedback", "mentor", "curator_reply", "competency",
    "off_topic", "unsafe",
)

INJECTION_RE = re.compile(
    r"(игнорируй|забудь|отмени)\s+(все\s+)?(предыдущ|свои|эти)\s*(инструкц|правил|команд)"
    r"|ignore\s+(all\s+)?(the\s+)?(previous|prior|above)\s+(instructions|rules|prompts)"
    r"|system\s*override|system\s*prompt|системн\w*\s+промпт"
    r"|ты\s+теперь\s+(админ|администратор|root)"
    r"|you\s+are\s+now\s+(an?\s+)?(admin|administrator|root)"
    r"|выдай\s+(свой\s+)?системн\w*\s+промпт"
    r"|отметь\s+(мне\s+)?(все|всё)\s+.{0,20}(выполнен|закрыт|сделан)",
    re.IGNORECASE)

_SECRET = re.compile(
    r"ghp_[0-9a-zA-Z]{10,}|xox[baprs]-[0-9a-zA-Z-]{10,}"
    r"|Bearer\s+[0-9a-zA-Z._~+/=-]{12,}|sk-[0-9a-zA-Z_-]{16,}"
    r"|(password|passwd|token|secret|api[_-]?key)\s*[:=]\s*\S+",
    re.IGNORECASE)

_ACCESS_WORDS = ("доступ", "доступа", "доступу", "права", "право", "доступ к",
                 "403", "forbidden", "не открыва", "не могу открыть",
                 "нет доступа", "заявк", "предостав")
_ACCESS_RIGHTS_WORD = re.compile(r"(?<!\w)прав(?!\w)", re.IGNORECASE)
_PROGRESS_WORDS = ("прогресс", "сколько закрыл", "сколько выполнил", "где я",
                   "статус", "процент", "закрыл", "выполнил", "сколько пунктов")
_NEXT_WORDS = ("что дальше", "дальше по", "следующий шаг", "следующ", "что делать",
               "с чего начать", "какой следующий", "куда двигаться", "что сейчас",
               "план на", "по чек-листу", "другую задачу", "новую задачу",
               "перейти к следующ", "переключиться на", "параллельно следующ")
_LEARN_WORDS = ("научи", "расскажи про", "объясни тему", "урок", "модуль",
                "квиз", "проверь меня", "вопросы для самопроверки", "изучить",
                "учиться", "обучение", "материал")
_PREPARE_WORDS = ("1:1", "один на один", "экватор", "встреч", "подготовить",
                  "подготовка", "презентац", "выпускн", "опрос", "собеседован")
_FEEDBACK_WORDS = ("обратная связь", "фидбек", "спросить у наставника",
                    "как спросить", "сформулируй вопрос", "помоги спросить",
                    "обратной связ", "сформулиру", "отзыв", "ревью моей",
                    "как решить задачу", "помоги решить задачу",
                    "разобраться с задач", "помоги с задач")
_MENTOR_WORDS = ("наставник", "куратор", "бадди", "не справляюсь", "слишком сложно",
                  "помогите человек", "живой человек", "позови", "эскалац",
                  "конфликт", "обидел", "плохо себя", "выгор", "устал", "устала",
                  "нет сил", "тяжело работать", "перегружен", "перегружена",
                  "надоело работать")
_TROUBLE_WORDS = ("ошибка", "не работает", "не собирается", "падает", "не запускается",
                  "красный", "сломал", "блокер", "застрял", "не получается",
                  "failed", "error", "почему не", "не скачивается", "не могу скачать",
                  "не загружается", "не грузится", "не открывается файл",
                  "файл не", "500", "502", "503")
_CURATOR_MARKERS = ("ответ куратора", "куратор ответил", "куратор написал",
                    "наставник ответил", "разбери ответ", "что он имел в виду",
                    "что она имела в виду", "объясни ответ", "прислал текст")
_COMPETENCY_WORDS = ("компетенц", "колесо", "самооценк", "оценить себя",
                     "зоны развития", "план развития", "оси")
_UNKNOWN_PATTERNS = (
    re.compile(r"sla|сла\b|внутренн\w* (api|url|endpoint|адрес|ip)", re.IGNORECASE),
    re.compile(r"(бонус|преми\w*|зарплат\w*|оклад)\s+(в|у|сколько|какой|какого)", re.IGNORECASE),
    re.compile(r"соседск\w* соглашени", re.IGNORECASE),
)


def classify(text: str) -> str:
    """Route text into the server's closed onboarding intent set."""
    lowered = " ".join(text.casefold().split())
    if INJECTION_RE.search(lowered) or _SECRET.search(text):
        return "unsafe"
    if any(marker in lowered for marker in _CURATOR_MARKERS):
        return "curator_reply"
    if any(word in lowered for word in _COMPETENCY_WORDS):
        return "competency"
    if (any(word in lowered for word in _ACCESS_WORDS)
            or _ACCESS_RIGHTS_WORD.search(lowered)):
        return "access"
    if any(word in lowered for word in _PROGRESS_WORDS):
        return "progress"
    if any(word in lowered for word in _PREPARE_WORDS):
        return "prepare"
    if any(word in lowered for word in _FEEDBACK_WORDS):
        return "feedback"
    if any(word in lowered for word in _MENTOR_WORDS):
        return "mentor"
    if any(word in lowered for word in _TROUBLE_WORDS):
        return "troubleshoot"
    if any(word in lowered for word in _LEARN_WORDS):
        return "learn"
    if any(word in lowered for word in _NEXT_WORDS):
        return "next_step"
    if any(pattern.search(lowered) for pattern in _UNKNOWN_PATTERNS):
        return "explain"
    return "explain"
