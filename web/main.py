from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from config import load_config
from db.models import Subject, Subtopic, Topic, WebLoginCode
from db.repo import Repo
from db.session import init_db, make_engine, make_sessionmaker

BASE_DIR = Path(__file__).resolve().parent

config = load_config()
engine = make_engine(config.db_url)
sm = make_sessionmaker(engine)
bot_client = Bot(token=config.bot_token)

app = FastAPI(title="Quiz Web")
app.add_middleware(SessionMiddleware, secret_key=config.web_session_secret)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
async def startup() -> None:
    await init_db(engine)


@app.on_event("shutdown")
async def shutdown() -> None:
    await bot_client.session.close()


def _code_hash(code: str) -> str:
    base = f"{code}:{config.web_session_secret}".encode("utf-8")
    return hashlib.sha256(base).hexdigest()


def _normalize_username(value: str) -> str:
    return value.strip().lstrip("@").lower()


def _render_index(request: Request, user: dict[str, Any] | None, error: str | None = None, info: str | None = None):
    pending_tg_id = request.session.get("pending_login_tg_id")
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "user": user,
            "error": error,
            "info": info,
            "pending_login": bool(pending_tg_id),
            "pending_tg_id": pending_tg_id,
            "pending_login_name": request.session.get("pending_login_name"),
        },
    )


async def _current_user(request: Request) -> dict[str, Any] | None:
    tg_id = request.session.get("tg_id")
    if not tg_id:
        return None

    async with sm() as s:
        repo = Repo(s)
        user = await repo.get_or_create_user(
            tg_id=int(tg_id),
            full_name=request.session.get("full_name", "-"),
        )
        is_db_admin = await repo.is_admin(user.tg_id)

    role = "user"
    if user.tg_id in config.admin_ids:
        role = "superadmin"
    elif is_db_admin:
        role = "admin"

    return {
        "id": user.id,
        "tg_id": user.tg_id,
        "full_name": user.full_name,
        "role": role,
    }


def _require_auth(user: dict[str, Any] | None) -> dict[str, Any]:
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _require_admin(user: dict[str, Any] | None) -> dict[str, Any]:
    usr = _require_auth(user)
    if usr["role"] not in {"admin", "superadmin"}:
        raise HTTPException(status_code=403, detail="Admin role required")
    return usr


def _require_superadmin(user: dict[str, Any] | None) -> dict[str, Any]:
    usr = _require_auth(user)
    if usr["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin role required")
    return usr


def _accuracy(correct: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((correct / total) * 100.0, 1)


def _streak_from_daily(daily: list[dict[str, Any]]) -> int:
    streak = 0
    for day in reversed(daily):
        solved = int(day["solved"])
        correct = int(day["correct"])
        if solved > 0 and solved == correct:
            streak += 1
        else:
            break
    return streak


async def _get_or_create_topic_by_name(repo: Repo, subject_id: int, name: str) -> int:
    q = await repo.s.execute(select(Topic).where(Topic.subject_id == subject_id, Topic.name == name.strip()))
    topic = q.scalar_one_or_none()
    if topic:
        return topic.id
    return await repo.create_topic(subject_id=subject_id, name=name)


async def _get_or_create_subtopic_by_name(repo: Repo, topic_id: int, name: str) -> int:
    q = await repo.s.execute(select(Subtopic).where(Subtopic.topic_id == topic_id, Subtopic.name == name.strip()))
    sub = q.scalar_one_or_none()
    if sub:
        return sub.id
    return await repo.create_subtopic(topic_id=topic_id, name=name)


def _parse_option_lines(raw: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for part in [p.strip() for p in raw.split("|") if p.strip()]:
        if ")" in part:
            label, txt = part.split(")", 1)
        elif "." in part:
            label, txt = part.split(".", 1)
        else:
            raise ValueError("options must contain labels like A) ...")
        out.append((label.strip().upper(), txt.strip()))
    if len(out) < 2:
        raise ValueError("at least 2 options required")
    return out


def _norm_labels(raw: str) -> set[str]:
    mp = {"А": "A", "Б": "B", "В": "C", "Г": "D"}
    parts = [x.strip().upper() for x in raw.replace(" ", "").split(",") if x.strip()]
    return {mp.get(x, x) for x in parts}


def _build_options_for_db(options_raw: list[tuple[str, str]], correct_labels: set[str]) -> list[tuple[str, bool]]:
    mp = {"А": "A", "Б": "B", "В": "C", "Г": "D"}
    out: list[tuple[str, bool]] = []
    for lbl, txt in options_raw:
        n = mp.get(lbl, lbl)
        out.append((txt, n in correct_labels))
    return out


@app.get("/")
async def index(request: Request):
    user = await _current_user(request)
    return _render_index(request, user)


@app.post("/auth/request-code")
async def auth_request_code(request: Request, telegram: str = Form(...)):
    user = await _current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=303)

    telegram_input = (telegram or "").strip()
    if not telegram_input:
        return _render_index(request, None, error="Укажите Telegram: @username или numeric tg_id.")

    async with sm() as s:
        repo = Repo(s)

        target_user = None
        if telegram_input.lstrip("+").isdigit():
            tg_id = int(telegram_input)
            target_user = await repo.get_user_by_tg_id(tg_id)
        else:
            uname = _normalize_username(telegram_input)
            target_user = await repo.get_user_by_username(uname)

        if target_user is None:
            return _render_index(
                request,
                None,
                error="Пользователь не найден. Сначала напишите боту /start с этого Telegram аккаунта.",
            )

        code = f"{secrets.randbelow(1_000_000):06d}"
        now = datetime.utcnow()
        rec = WebLoginCode(
            tg_id=target_user.tg_id,
            code_hash=_code_hash(code),
            expires_at=now + timedelta(minutes=10),
        )
        s.add(rec)
        await s.commit()

    try:
        await bot_client.send_message(
            chat_id=target_user.tg_id,
            text=(
                "Код входа на сайт: "
                f"{code}\n\n"
                "Код действует 10 минут. Никому его не передавайте."
            ),
        )
    except TelegramAPIError:
        return _render_index(
            request,
            None,
            error="Бот не смог отправить код. Убедитесь, что вы писали боту /start и не блокировали его.",
        )

    request.session["pending_login_tg_id"] = target_user.tg_id
    request.session["pending_login_name"] = target_user.full_name

    return _render_index(request, None, info="Код отправлен в Telegram. Введите его ниже.")


@app.post("/auth/verify-code")
async def auth_verify_code(request: Request, code: str = Form(...)):
    user = await _current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=303)

    pending_tg_id = request.session.get("pending_login_tg_id")
    if not pending_tg_id:
        return _render_index(request, None, error="Сначала запросите код.")

    token = (code or "").strip()
    if not token.isdigit() or len(token) != 6:
        return _render_index(request, None, error="Код должен быть из 6 цифр.")

    now = datetime.utcnow()
    async with sm() as s:
        q = await s.execute(
            select(WebLoginCode)
            .where(
                WebLoginCode.tg_id == int(pending_tg_id),
                WebLoginCode.code_hash == _code_hash(token),
                WebLoginCode.used_at.is_(None),
                WebLoginCode.expires_at > now,
            )
            .order_by(WebLoginCode.id.desc())
        )
        rec = q.scalar_one_or_none()

        if rec is None:
            return _render_index(request, None, error="Неверный или просроченный код.")

        rec.used_at = now

        repo = Repo(s)
        db_user = await repo.get_user_by_tg_id(int(pending_tg_id))
        if db_user is None:
            return _render_index(request, None, error="Пользователь не найден. Напишите боту /start.")

        await s.commit()

    request.session["tg_id"] = int(pending_tg_id)
    request.session["full_name"] = db_user.full_name
    request.session.pop("pending_login_tg_id", None)
    request.session.pop("pending_login_name", None)

    return RedirectResponse(url="/", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@app.get("/solve")
async def solve_select(request: Request):
    user = await _current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    async with sm() as s:
        repo = Repo(s)
        subjects = await repo.get_subjects()

    return templates.TemplateResponse(
        request,
        "solve_select.html",
        {
            "request": request,
            "user": user,
            "subjects": subjects,
            "topics": [],
            "subtopics": [],
            "selected_subject_id": None,
            "selected_topic_id": None,
        },
    )


@app.get("/solve/subject/{subject_id}")
async def solve_select_topic(request: Request, subject_id: int):
    user = await _current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    async with sm() as s:
        repo = Repo(s)
        subjects = await repo.get_subjects()
        topics = await repo.get_topics(subject_id)

    return templates.TemplateResponse(
        request,
        "solve_select.html",
        {
            "request": request,
            "user": user,
            "subjects": subjects,
            "topics": topics,
            "subtopics": [],
            "selected_subject_id": subject_id,
            "selected_topic_id": None,
        },
    )


@app.get("/solve/question")
async def solve_question(request: Request):
    user = await _current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    subject_id = request.session.get("solve_subject_id")
    topic_id = request.session.get("solve_topic_id")
    if not subject_id or not topic_id:
        return RedirectResponse(url="/solve", status_code=303)

    subtopic_ids = request.session.get("solve_subtopic_ids") or []

    async with sm() as s:
        repo = Repo(s)
        db_user = await repo.get_or_create_user(tg_id=user["tg_id"], full_name=user["full_name"])

        current_qid = request.session.get("current_qid")
        if current_qid:
            q = await repo.get_question(current_qid)
            if q is None:
                request.session["current_qid"] = None
                current_qid = None

        if not current_qid:
            qid = await repo.pick_next_question_id(
                user_id=db_user.id,
                subject_id=subject_id,
                topic_id=topic_id,
                subtopic_ids=subtopic_ids or None,
            )
            if qid is None:
                return templates.TemplateResponse(
                    request,
                    "solve_done.html",
                    {
                        "request": request,
                        "user": user,
                        "total": request.session.get("solve_total", 0),
                        "correct": request.session.get("solve_correct", 0),
                    },
                )
            request.session["current_qid"] = qid
            q = await repo.get_question(qid)

        opts = await repo.get_options(q.id)

    return templates.TemplateResponse(
        request,
        "solve_question.html",
        {
            "request": request,
            "user": user,
            "question": q,
            "options": opts,
            "total": request.session.get("solve_total", 0),
            "correct": request.session.get("solve_correct", 0),
        },
    )


@app.get("/solve/topic/{subject_id}/{topic_id}")
async def solve_select_subtopics(request: Request, subject_id: int, topic_id: int):
    user = await _current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    async with sm() as s:
        repo = Repo(s)
        subjects = await repo.get_subjects()
        topics = await repo.get_topics(subject_id)
        subtopics = await repo.get_subtopics(topic_id)

    return templates.TemplateResponse(
        request,
        "solve_select.html",
        {
            "request": request,
            "user": user,
            "subjects": subjects,
            "topics": topics,
            "subtopics": subtopics,
            "selected_subject_id": subject_id,
            "selected_topic_id": topic_id,
        },
    )


@app.post("/solve/start")
async def solve_start(request: Request, subject_id: int = Form(...), topic_id: int = Form(...), subtopic_ids: list[int] = Form(default=[])):
    user = await _current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    request.session["solve_subject_id"] = subject_id
    request.session["solve_topic_id"] = topic_id
    request.session["solve_subtopic_ids"] = subtopic_ids
    request.session["solve_total"] = 0
    request.session["solve_correct"] = 0
    request.session["current_qid"] = None

    return RedirectResponse(url="/solve/question", status_code=303)


@app.post("/solve/answer")
async def solve_answer(request: Request, option_ids: list[int] = Form(default=[])):
    user = await _current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    qid = request.session.get("current_qid")
    if not qid:
        return RedirectResponse(url="/solve/question", status_code=303)

    chosen = sorted({int(x) for x in option_ids})
    if not chosen:
        raise HTTPException(status_code=400, detail="Choose at least one option")

    async with sm() as s:
        repo = Repo(s)
        q = await repo.get_question(qid)
        if not q:
            request.session["current_qid"] = None
            return RedirectResponse(url="/solve/question", status_code=303)

        correct_ids = await repo.get_correct_option_ids(qid)
        is_correct = set(chosen) == correct_ids

        db_user = await repo.get_or_create_user(tg_id=user["tg_id"], full_name=user["full_name"])
        await repo.add_attempt(db_user.id, qid, is_correct, chosen)

    request.session["solve_total"] = int(request.session.get("solve_total", 0)) + 1
    if is_correct:
        request.session["solve_correct"] = int(request.session.get("solve_correct", 0)) + 1
    request.session["current_qid"] = None

    return templates.TemplateResponse(
        request,
        "solve_result.html",
        {
            "request": request,
            "user": user,
            "is_correct": is_correct,
            "explanation": q.explanation,
            "total": request.session.get("solve_total", 0),
            "correct": request.session.get("solve_correct", 0),
        },
    )


@app.get("/stats")
async def stats_page(request: Request):
    user = await _current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    async with sm() as s:
        repo = Repo(s)
        db_user = await repo.get_or_create_user(tg_id=user["tg_id"], full_name=user["full_name"])
        total, correct = await repo.user_totals(db_user.id)
        by_topic = await repo.solved_by_topic(db_user.id, limit=8)
        by_day_raw = await repo.accuracy_by_day(db_user.id, days=14)
        recent = await repo.recent_attempts(db_user.id, limit=10)

    by_day_map = {d: (solved, corr) for d, solved, corr in by_day_raw}
    days: list[dict[str, Any]] = []
    for i in range(13, -1, -1):
        date_key = (datetime.utcnow() - timedelta(days=i)).date().isoformat()
        solved, corr = by_day_map.get(date_key, (0, 0))
        days.append(
            {
                "date": date_key[5:],
                "solved": solved,
                "correct": corr,
                "accuracy": _accuracy(corr, solved),
            }
        )

    topic_total = sum(cnt for _, cnt in by_topic) or 1
    topic_items = [
        {"name": name, "count": cnt, "pct": round((cnt / topic_total) * 100.0, 1)}
        for name, cnt in by_topic
    ]

    week_total = sum(d["solved"] for d in days[-7:])
    week_correct = sum(d["correct"] for d in days[-7:])
    best_day = max(days, key=lambda x: x["solved"]) if days else {"date": "-", "solved": 0}
    streak = _streak_from_daily(days)

    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            "request": request,
            "user": user,
            "total": total,
            "correct": correct,
            "accuracy": _accuracy(correct, total),
            "week_total": week_total,
            "week_correct": week_correct,
            "week_accuracy": _accuracy(week_correct, week_total),
            "best_day": best_day,
            "streak": streak,
            "days": days,
            "topic_items": topic_items,
            "recent": recent,
        },
    )


@app.get("/admin/import")
async def admin_import_page(request: Request):
    current = await _current_user(request)
    if not current:
        return RedirectResponse(url="/", status_code=303)
    user = _require_admin(current)
    return templates.TemplateResponse(
        request,
        "admin_import.html",
        {
            "request": request,
            "user": user,
            "report": None,
        },
    )


@app.get("/admin/broadcast")
async def admin_broadcast_page(request: Request):
    current = await _current_user(request)
    if not current:
        return RedirectResponse(url="/", status_code=303)
    user = _require_superadmin(current)

    async with sm() as s:
        repo = Repo(s)
        total_users = len(await repo.list_user_tg_ids())

    return templates.TemplateResponse(
        request,
        "admin_broadcast.html",
        {
            "request": request,
            "user": user,
            "total_users": total_users,
            "error": None,
            "report": None,
            "draft": "",
        },
    )


@app.post("/admin/broadcast")
async def admin_broadcast_send(
    request: Request,
    text: str = Form(...),
    send_confirm: str | None = Form(default=None),
):
    current = await _current_user(request)
    if not current:
        return RedirectResponse(url="/", status_code=303)
    user = _require_superadmin(current)

    async with sm() as s:
        repo = Repo(s)
        total_users = len(await repo.list_user_tg_ids())

    msg = (text or "").strip()
    if len(msg) < 3:
        return templates.TemplateResponse(
            request,
            "admin_broadcast.html",
            {
                "request": request,
                "user": user,
                "total_users": total_users,
                "error": "Слишком короткий текст рассылки.",
                "report": None,
                "draft": msg,
            },
        )
    if len(msg) > 3500:
        return templates.TemplateResponse(
            request,
            "admin_broadcast.html",
            {
                "request": request,
                "user": user,
                "total_users": total_users,
                "error": "Слишком длинный текст (лимит 3500 символов).",
                "report": None,
                "draft": msg,
            },
        )
    if send_confirm != "yes":
        return templates.TemplateResponse(
            request,
            "admin_broadcast.html",
            {
                "request": request,
                "user": user,
                "total_users": total_users,
                "error": "Подтверди отправку чекбоксом.",
                "report": None,
                "draft": msg,
            },
        )

    async with sm() as s:
        repo = Repo(s)
        tg_ids = await repo.list_user_tg_ids()

    sent = 0
    failed = 0
    skipped_self = 0
    failed_ids: list[int] = []

    for tg_id in tg_ids:
        if tg_id == user["tg_id"]:
            skipped_self += 1
            continue
        try:
            await bot_client.send_message(chat_id=tg_id, text=msg)
            sent += 1
            await asyncio.sleep(0.03)
        except TelegramRetryAfter as e:
            await asyncio.sleep(float(e.retry_after) + 0.2)
            try:
                await bot_client.send_message(chat_id=tg_id, text=msg)
                sent += 1
            except Exception:
                failed += 1
                if len(failed_ids) < 20:
                    failed_ids.append(tg_id)
        except (TelegramForbiddenError, TelegramBadRequest, TelegramAPIError):
            failed += 1
            if len(failed_ids) < 20:
                failed_ids.append(tg_id)
        except Exception:
            failed += 1
            if len(failed_ids) < 20:
                failed_ids.append(tg_id)

    report = {
        "sent": sent,
        "failed": failed,
        "skipped_self": skipped_self,
        "failed_ids": failed_ids,
    }

    return templates.TemplateResponse(
        request,
        "admin_broadcast.html",
        {
            "request": request,
            "user": user,
            "total_users": len(tg_ids),
            "error": None,
            "report": report,
            "draft": "",
        },
    )


@app.post("/admin/import")
async def admin_import_upload(request: Request, file: UploadFile):
    current = await _current_user(request)
    if not current:
        return RedirectResponse(url="/", status_code=303)
    user = _require_admin(current)

    raw = await file.read()
    name = (file.filename or "").lower()
    created = 0
    errors: list[str] = []

    async with sm() as s:
        repo = Repo(s)

        if name.endswith(".json"):
            try:
                payload = json.loads(raw.decode("utf-8-sig"))
                if not isinstance(payload, list):
                    raise ValueError("JSON root must be a list")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

            rows = payload
        elif name.endswith(".csv"):
            text = raw.decode("utf-8-sig")
            rows = list(csv.DictReader(text.splitlines()))
        else:
            raise HTTPException(status_code=400, detail="Only .csv or .json supported")

        for i, row in enumerate(rows, start=1):
            try:
                subject_code = str(row.get("subject_code", "")).strip().lower()
                subject_name = str(row.get("subject_name", "")).strip() or subject_code
                topic_name = str(row.get("topic_name", "")).strip()
                subtopic_name = str(row.get("subtopic_name", "")).strip()
                qtype = str(row.get("qtype", "single")).strip().lower()
                text_q = str(row.get("question_text", "")).strip()
                explanation = str(row.get("explanation", "")).strip() or "-"

                if qtype not in {"single", "multi"}:
                    raise ValueError("qtype must be single or multi")
                if not subject_code or not topic_name or not text_q:
                    raise ValueError("subject_code/topic_name/question_text are required")

                subj = await repo.get_subject_by_code(subject_code)
                if subj is None:
                    sid = await repo.create_subject(subject_code, subject_name)
                else:
                    sid = subj.id

                tid = await _get_or_create_topic_by_name(repo, sid, topic_name)
                stid = None
                if subtopic_name:
                    stid = await _get_or_create_subtopic_by_name(repo, tid, subtopic_name)

                raw_options = row.get("options")
                if isinstance(raw_options, list):
                    options_raw = [(chr(65 + idx), str(v)) for idx, v in enumerate(raw_options)]
                elif isinstance(raw_options, dict):
                    options_raw = [(str(k).upper(), str(v)) for k, v in raw_options.items()]
                else:
                    options_raw = _parse_option_lines(str(raw_options or ""))

                if len(options_raw) < 2:
                    raise ValueError("need at least 2 options")

                raw_correct = row.get("correct")
                if isinstance(raw_correct, list):
                    correct_labels = {str(x).strip().upper() for x in raw_correct}
                else:
                    correct_labels = _norm_labels(str(raw_correct or ""))

                if not correct_labels:
                    raise ValueError("correct is required")

                options_for_db = _build_options_for_db(options_raw, correct_labels)

                if qtype == "single" and sum(1 for _, c in options_for_db if c) != 1:
                    raise ValueError("single question must have exactly one correct option")

                if sum(1 for _, c in options_for_db if c) == 0:
                    raise ValueError("no correct option resolved")

                await repo.create_question(
                    subject_id=sid,
                    topic_id=tid,
                    subtopic_id=stid,
                    text=text_q,
                    qtype=qtype,
                    explanation=explanation,
                    image_file_id=None,
                    options=options_for_db,
                )
                created += 1
            except Exception as e:
                errors.append(f"line {i}: {e}")

    report = {
        "created": created,
        "failed": len(errors),
        "errors": errors[:50],
    }

    return templates.TemplateResponse(
        request,
        "admin_import.html",
        {
            "request": request,
            "user": user,
            "report": report,
        },
    )
