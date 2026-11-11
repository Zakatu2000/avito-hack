# -*- coding: utf-8 -*-
"""Build normalized onboarding fixtures from the source materials.

Inputs (local machine only, never required in Docker/CI):
- the intern checklist XLSX (all rows are preserved verbatim);
- the extracted Gemini report pack already committed under server/fixtures/gemini_report/.

Outputs (committed, consumed by server.store seed and scripts/checklist_coverage.py):
- server/fixtures/sources/xlsx_snapshot.json  (raw cell snapshot, provenance)
- server/fixtures/checklist_catalog.json      (normalized catalog, 100% of rows)
- server/fixtures/gemini_report/images/manifest.json (hashes + alt text)

The original C# OOP course PDF referenced by the Gemini report is NOT available
locally; the course modules are reconstructed from the report's own CHK-16..23
table and marked source_status="reconstructed" (never invent unavailable content).
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "server" / "fixtures"
SNAPSHOT = FIXTURES / "sources" / "xlsx_snapshot.json"
CATALOG = FIXTURES / "checklist_catalog.json"
GEMINI = FIXTURES / "gemini_report"

DEFAULT_XLSX = r"C:\Users\kompukter\Downloads\Чек-лист стажера.xlsx"

STAGE_BY_LABEL = {
    "1 неделя": ("week-1", 1),
    "2 неделя": ("week-2", 2),
    "1 месяц": ("month-1", 3),
    "2 месяц": ("month-2", 4),
    "3 месяц": ("month-3", 5),
    "после 3-х месяцев": ("after-month-3", 6),
}

# Mentor/curator-facing rows still belong to the intern's lifecycle: the buddy
# tracks them as "waiting on the human" items (actor shows who must act).
MENTOR_MARKERS = ("наставник", "бадди", "руководител", "куратор", "дай обратную связь", "обсуди со стажёром")


def norm_stage(label):
    key = (label or "").strip().casefold()
    for src, (code, order) in STAGE_BY_LABEL.items():
        if src in key:
            return code, order
    raise ValueError(f"unknown stage label: {label!r}")


def split_instructions(text):
    """Numbered '1. ... 2. ...' cells become an ordered instruction list."""
    if not text:
        return []
    parts = re.split(r"(?:^|\s)(\d+)\.\s+", text)
    if len(parts) < 3:
        return [text.strip()]
    out = []
    for i in range(1, len(parts) - 1, 2):
        body = parts[i + 1].strip()
        if body:
            out.append(body)
    return out


def guess_actor(title, description):
    hay = f"{title} {description}".casefold()
    if any(m in hay for m in ("на 1:1 обсуди со стажёром", "дай обратную связь", "проверь презентацию стажёра", "напутственное слово")):
        return "mentor"
    if "бадди" in hay and ("сходи на бриф" in hay or "поддержи его" in hay):
        return "mentor"
    if any(m in hay for m in ("добавь стажёра", "назначь со стажёром", "запросил ли стажёр")):
        return "mentor"
    return "intern"


def build_snapshot(xlsx_path):
    import openpyxl  # dev-only dependency

    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    sheets = {}
    for name in wb.sheetnames:
        ws = wb[name]
        rows = []
        for row in ws.iter_rows(min_row=2):
            cells = {}
            for cell in row:
                if cell.value is not None and str(cell.value).strip():
                    cells[cell.coordinate] = str(cell.value).strip()
            if cells:
                rows.append({"row": row[0].row, "cells": cells})
        sheets[name] = rows
    return {
        "sourceFile": Path(xlsx_path).name,
        "capturedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sheets": sheets,
    }


def catalog_common(rows):
    items = []
    for entry in rows:
        cells = entry["cells"]
        title = cells.get(f"A{entry['row']}", "").strip()
        desc = cells.get(f"B{entry['row']}", "").strip()
        stage_label = cells.get(f"C{entry['row']}", "").strip()
        # The B/C columns shift when the description column is empty.
        if not stage_label and desc:
            for label in STAGE_BY_LABEL:
                if desc.casefold().startswith(label):
                    stage_label, desc = desc, ""
                    break
        if not title or not stage_label:
            continue
        stage, order = norm_stage(stage_label)
        items.append({
            "id": f"common-{len(items)+1:02d}",
            "track": "common",
            "title": title,
            "originalText": title,
            "description": desc,
            "instructions": split_instructions(desc),
            "stage": stage,
            "stageOrder": order,
            "stageLabel": stage_label,
            "actor": guess_actor(title, desc),
            "prerequisites": [],
            "objective": "",
            "evidence": "",
            "completionPolicy": "self_confirmed",
            "sourceRef": {"sheet": "Материалы для всех", "row": entry["row"]},
        })
    return items


def catalog_backend(rows):
    items = []
    for entry in rows:
        cells = entry["cells"]
        title = cells.get(f"A{entry['row']}", "").strip()
        stage_label = cells.get(f"B{entry['row']}", "").strip()
        if not title or not stage_label:
            continue
        stage, order = norm_stage(stage_label)
        items.append({
            "id": f"backend-{len(items)+1:02d}",
            "track": "backend",
            "title": title.split("\n")[0].strip(),
            "originalText": title,
            "description": "",
            "instructions": split_instructions(title),
            "stage": stage,
            "stageOrder": order,
            "stageLabel": stage_label,
            "actor": "intern",
            "prerequisites": [],
            "objective": "",
            "evidence": "",
            "completionPolicy": "self_confirmed",
            "sourceRef": {"sheet": "Чек-лист Backend", "row": entry["row"]},
        })
    return items


def gemini_track_items():
    """Analytics/Marketing tracks come from the Gemini report (CHK-25/CHK-27):
    the XLSX has no rows for them and inventing XLSX rows is forbidden."""
    return [
        {
            "id": "analytics-01", "track": "analytics",
            "title": "Профильный модуль: стек данных, единый источник правды (SSOT), Tableau и метрики продукта",
            "originalText": "CHK-25: Профильный модуль (Аналитика и DS): Стек данных, единый источник правды (SSOT), Tableau и метрики продукта",
            "description": "SQL, Python, Tableau, валидация данных и расчёт продуктовых метрик; ссылка на проверенный дашборд или ноутбук как доказательство.",
            "instructions": [], "stage": "month-1", "stageOrder": 3, "stageLabel": "2–5 неделя",
            "actor": "intern", "prerequisites": [], "objective": "", "evidence": "",
            "completionPolicy": "curator_confirmed",
            "sourceRef": {"sheet": "gemini-report", "row": "CHK-25"},
        },
        {
            "id": "analytics-02", "track": "analytics",
            "title": "Колесо компетенций аналитика: самооценка по 8 осям и план развития",
            "originalText": "Gemini report: competency assessment (Semantic Mastery Store) + практика «Колесо компетенций» из задания",
            "description": "Выбрать направление аналитики, оценить себя по 8 осям (0–10), выбрать 1–2 зоны развития и составить план действий со сроками.",
            "instructions": [], "stage": "month-1", "stageOrder": 3, "stageLabel": "2–5 неделя",
            "actor": "intern", "prerequisites": [], "objective": "", "evidence": "",
            "completionPolicy": "evidence_required",
            "sourceRef": {"sheet": "gemini-report", "row": "competency_assessment"},
        },
        {
            "id": "marketing-01", "track": "marketing",
            "title": "Профильный модуль: воронки привлечения, CRM-коммуникации, Tone of Voice и аналитика кампаний",
            "originalText": "CHK-27: Профильный модуль (Маркетинг и коммуникации): Воронки привлечения, CRM-коммуникации, тон голоса бренда (Tone of Voice) и аналитика кампаний",
            "description": "CAC, LTV, Retention, CTR; утверждённый бриф кампании и отчёт по тестовому запуску как доказательство.",
            "instructions": [], "stage": "month-1", "stageOrder": 3, "stageLabel": "2–5 неделя",
            "actor": "intern", "prerequisites": [], "objective": "", "evidence": "",
            "completionPolicy": "curator_confirmed",
            "sourceRef": {"sheet": "gemini-report", "row": "CHK-27"},
        },
    ]


def images_manifest():
    alt = {
        "image6.png": "Архитектурная диаграмма AI-Buddy: Guardrail → Orchestrator/Planner → Hybrid RAG (Playbook, Checklist, C# OOP) → Typed Tool Executor с HITL Preview & Confirm Gate → Mock Sandbox (Access, Jira, Messenger) и Audit Log.",
        "image7.png": "Инфографика покрытия: 32 eval-кейса по 9 категориям (функциональные 12, эпистемические 7, безопасность 7, транзакционные 6) и индекс зрелости стека (LangGraph+MCP 95/92, PostgreSQL+pgvector 94/98, Outbox FSM 98/96, DeepEval 96/94, OTel+Phoenix 97/95).",
        "image9.png": "Инфографика структуры адаптации: 200+ команд, 200–250 релизов/день, 20 ч/нед, коридор OKR 0.6–0.7; индекс автономности E1→E2; распределение 30 пунктов чек-листа по этапам и доля HITL.",
    }
    entries = []
    for png in sorted((GEMINI / "images").glob("*.png")):
        data = png.read_bytes()
        entries.append({
            "file": png.name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "altText": alt.get(png.name, ""),
            "relationship": {"image6.png": "rId9", "image7.png": "rId12", "image9.png": "rId6"}.get(png.name),
        })
    return {
        "sourceDocx": "source.docx",
        "sourceDocxSha256": hashlib.sha256((GEMINI / "source.docx").read_bytes()).hexdigest(),
        "extractedText": "extracted_text.txt",
        "extractedTextSha256": hashlib.sha256((GEMINI / "extracted_text.txt").read_bytes()).hexdigest(),
        "images": entries,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", default=DEFAULT_XLSX)
    parser.add_argument("--snapshot-only", action="store_true")
    args = parser.parse_args()

    snapshot = build_snapshot(args.xlsx)
    SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    sheets = snapshot["sheets"]
    common = catalog_common(sheets.get("Материалы для всех", []))
    backend = catalog_backend(sheets.get("Чек-лист Backend", []))
    catalog = {
        "version": "checklist-v1",
        "generatedAt": snapshot["capturedAt"],
        "source": {"type": "xlsx", "file": snapshot["sourceFile"], "snapshot": "sources/xlsx_snapshot.json"},
        "stages": [
            {"code": code, "label": label, "order": order}
            for label, (code, order) in sorted(STAGE_BY_LABEL.items(), key=lambda kv: kv[1][1])
        ],
        "tracks": ["common", "backend", "analytics", "marketing"],
        "items": common + backend + gemini_track_items(),
    }
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    (GEMINI / "images" / "manifest.json").write_text(
        json.dumps(images_manifest(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"catalog: {len(common)} common + {len(backend)} backend + {len(gemini_track_items())} gemini-track items")
    print(f"xlsx rows: {sum(len(v) for v in sheets.values())}")


if __name__ == "__main__":
    main()
