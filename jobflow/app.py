"""Same-origin authenticated local application. Public demo never imports this server."""

import asyncio
import json
import math
import os
import re
import secrets
import time
from contextlib import asynccontextmanager, closing
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .integrations import Monitor, notify
from .matching import DEFAULT_WEIGHTS
from .parsing import parse, skills_in
from .storage import Store, dumps, now
from .studio import draft_letter, export_cv, import_cv, tailored_cv

ROOT = Path(__file__).resolve().parent.parent


def create_app(data_dir=None, bootstrap=None, testing=False):
    if not testing:
        load_dotenv(ROOT / ".env")
    data_dir = Path(data_dir or os.getenv("JOBFLOW_DATA_DIR", str(ROOT / "private"))).resolve()
    store = Store(data_dir / "jobflow.sqlite")
    bootstrap = bootstrap or secrets.token_urlsafe(32)
    sessions = {}
    monitor = Monitor(store, data_dir)
    allowed_origins = {"http://127.0.0.1:8765", "http://localhost:8765"}
    if testing:
        allowed_origins.add("http://testserver")

    @asynccontextmanager
    async def lifespan(app):
        with store.connect() as db:
            db.execute(
                "UPDATE outbox SET status='delivery_unknown',error='Interrupted delivery; inspect bot before manual retry' WHERE status='sending'"
            )
        task = None if testing else asyncio.create_task(monitor.loop())
        yield
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            await monitor.stop()

    app = FastAPI(
        title="JobFlow AI local API", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.store = store
    app.state.monitor = monitor
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"] + (["testserver"] if testing else [])
    )

    @app.middleware("http")
    async def protect(request, call_next):
        if request.url.path.startswith("/api/"):
            if request.headers.get("origin") not in allowed_origins and request.method != "GET":
                return JSONResponse({"detail": "Untrusted origin"}, status_code=403)
            if request.url.path != "/api/bootstrap":
                session = sessions.get(request.cookies.get("jobflow_session", ""))
                if not session or session["expires"] < time.time():
                    return JSONResponse({"detail": "Launch JobFlow locally to sign in"}, status_code=401)
                if request.method != "GET" and not secrets.compare_digest(
                    request.headers.get("x-jobflow-csrf", ""), session["csrf"]
                ):
                    return JSONResponse({"detail": "Invalid CSRF token"}, status_code=403)
            if int(request.headers.get("content-length", "0") or 0) > 11 * 1024 * 1024:
                return JSONResponse({"detail": "Request exceeds 11 MB"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.post("/api/bootstrap")
    async def bootstrap_login(request: Request):
        nonlocal bootstrap
        body = await request.json()
        if not bootstrap or not secrets.compare_digest(str(body.get("token", "")), bootstrap):
            raise HTTPException(401, "Invalid or already used launch token")
        bootstrap = None
        sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        sessions[sid] = {"csrf": csrf, "expires": time.time() + 8 * 3600}
        response = JSONResponse({"csrf": csrf})
        response.set_cookie("jobflow_session", sid, httponly=True, samesite="strict", max_age=8 * 3600)
        return response

    @app.get("/api/session")
    async def session(request: Request):
        return {"csrf": sessions[request.cookies["jobflow_session"]]["csrf"]}

    @app.post("/api/logout")
    async def logout(request: Request):
        sessions.pop(request.cookies.get("jobflow_session", ""), None)
        response = JSONResponse({"ok": True})
        response.delete_cookie("jobflow_session")
        return response

    @app.get("/api/state")
    async def state():
        jobs = store.jobs()
        app_rows = store.rows("SELECT * FROM applications ORDER BY updated_at DESC")
        app_job_ids = {a["job_id"] for a in app_rows}
        return {
            "mode": "private-test" if testing else "private",
            "jobs": jobs[:1000] + [j for j in jobs[1000:] if j["id"] in app_job_ids],
            "total_jobs": len(jobs),
            "sources": store.rows("SELECT * FROM sources ORDER BY username"),
            "profile": store.get("profile"),
            "preferences": store.get("preferences"),
            "cvs": store.rows("SELECT id,label,text,created_at,parent_id FROM cvs ORDER BY id DESC"),
            "letters": store.rows("SELECT * FROM letters ORDER BY id DESC"),
            "applications": app_rows,
            "events": store.rows("SELECT * FROM status_events ORDER BY at,id"),
            "analytics": store.analytics(),
            "outbox": store.rows(
                "SELECT id,kind,status,created_at,sent_at,error FROM outbox ORDER BY id DESC LIMIT 100"
            ),
            "telegram": monitor.state,
        }

    @app.get("/api/jobs")
    async def jobs(q: str = "", country: str = "", role: str = "", page: int = 1, minimum: float = 0):
        filtered = [
            j
            for j in store.jobs()
            if not j["unavailable"]
            and q.lower() in (str(j.get("title") or "") + " " + j["original_text"]).lower()
            and (not country or j.get("country") == country)
            and (not role or j.get("role") == role)
            and j["matching"]["score"] >= minimum
        ]
        page = max(1, page)
        return {
            "items": filtered[(page - 1) * 50 : page * 50],
            "total": len(filtered),
            "page": page,
            "page_size": 50,
        }

    @app.post("/api/sources")
    async def sources(request: Request):
        body = await request.json()
        username = str(body.get("username", "")).lstrip("@")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,31}", username):
            raise ValueError("Invalid Telegram channel username")
        with store.connect() as db:
            db.execute(
                "INSERT INTO sources(username,enabled) VALUES(?,?) ON CONFLICT(username) DO UPDATE SET enabled=excluded.enabled",
                (username, int(bool(body.get("enabled")))),
            )
        return {"ok": True}

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: int):
        job = store.job(job_id)
        if not job:
            raise HTTPException(404, "Vacancy not found")
        return job

    @app.post("/api/sync")
    async def sync():
        if testing:
            return {"state": "Test mode · Telegram disabled"}
        return await monitor.sync()

    @app.post("/api/import-message")
    async def import_message(request: Request):
        body = await request.json()
        source_id = int(body["source_id"])
        if not store.rows("SELECT id FROM sources WHERE id=?", (source_id,)):
            raise ValueError("Source not found")
        return store.ingest(
            source_id,
            int(body["message_id"]),
            str(body["text"])[:20000],
            body.get("published_at") or now(),
            body.get("original_url"),
            advance=False,
        )

    @app.patch("/api/jobs/{job_id}")
    async def correct_job(job_id: int, request: Request):
        job = store.job(job_id)
        if not job:
            raise HTTPException(404, "Vacancy not found")
        fields = await request.json()
        allowed = set(parse("")) - {"classification", "extraction_method"}
        if not set(fields) <= allowed:
            raise ValueError("Unsupported vacancy field")
        if any(isinstance(v, str) and len(v) > 1500 for v in fields.values()):
            raise ValueError("Field exceeds 1,500 characters")
        for key, value in fields.items():
            if value is None:
                continue
            if key in ("required_skills", "nice_skills"):
                if (
                    not isinstance(value, list)
                    or len(value) > 50
                    or any(not isinstance(v, str) or len(v) > 120 for v in value)
                ):
                    raise ValueError("Skills must be a list of short text values")
            elif key in ("salary_min", "salary_max", "years_experience"):
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                    raise ValueError("Numeric vacancy fields must be finite and nonnegative")
            elif key in ("relocation", "country_restricted", "german_required", "repost"):
                if type(value) is not bool:
                    raise ValueError("Vacancy flags must be boolean or unknown")
            elif not isinstance(value, str):
                raise ValueError("Vacancy text fields must be text or unknown")
        with store.connect() as db:
            previous = json.loads(
                db.execute("SELECT manual_fields FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
            )
            previous.update(fields)
            db.execute(
                "UPDATE jobs SET manual_fields=?,updated_at=? WHERE id=?", (dumps(previous), now(), job_id)
            )
        return {"ok": True}

    @app.post("/api/profile")
    async def profile(request: Request):
        body = await request.json()
        current = store.get("profile")
        if not set(body) <= set(current):
            raise ValueError("Unsupported profile field")
        current.update(body)
        if (
            not isinstance(current["name"], str)
            or len(current["name"]) > 120
            or type(current["relocation_required"]) is not bool
        ):
            raise ValueError("Invalid name or relocation preference")
        if not isinstance(current["languages"], dict) or any(
            not isinstance(k, str) or not isinstance(v, str) or len(k) > 50 or len(v) > 50
            for k, v in current["languages"].items()
        ):
            raise ValueError("Language levels must be short text values")
        for key in ("roles", "countries", "formats", "excluded_companies", "excluded_industries"):
            if (
                not isinstance(current[key], list)
                or len(current[key]) > 50
                or any(not isinstance(v, str) or len(v) > 120 for v in current[key])
            ):
                raise ValueError("Profile preferences must be lists of short text values")
        for key in ("years_experience", "salary_min"):
            value = current[key]
            if value is not None and (
                type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1000000
            ):
                raise ValueError("Experience and salary must be nonnegative numbers or unknown")
        if current["authorized_countries"] is not None and (
            not isinstance(current["authorized_countries"], list)
            or any(not isinstance(v, str) for v in current["authorized_countries"])
        ):
            raise ValueError("Work authorization must be a country list or unknown")
        weights = current.get("weights") or DEFAULT_WEIGHTS
        if (
            set(weights) != set(DEFAULT_WEIGHTS)
            or any(not isinstance(v, (int, float)) or not 0 <= v <= 100 for v in weights.values())
            or sum(weights.values()) <= 0
        ):
            raise ValueError("Matching weights must be nonnegative, finite and sum above zero")
        if not isinstance(current.get("facts", []), list) or len(current.get("facts", [])) > 100:
            raise ValueError("Maximum 100 profile facts")
        for fact in current.get("facts", []):
            if (
                not isinstance(fact, dict)
                or not isinstance(fact.get("text"), str)
                or not isinstance(fact.get("id"), str)
                or type(fact.get("approved")) is not bool
            ):
                raise ValueError("Invalid factual statement")
            if (
                fact.get("status") not in ("verified", "self_reported", "inferred")
                or not fact.get("id")
                or len(fact.get("text", "")) > 1500
                or not isinstance(fact.get("skills", []), list)
            ):
                raise ValueError("Invalid factual statement")
            if any(not isinstance(v, str) or len(v) > 120 for v in fact.get("skills", [])):
                raise ValueError("Fact skills must be short text values")
            if fact["status"] == "verified":
                cv = store.rows("SELECT text FROM cvs WHERE id=?", (fact.get("cv_id"),))
                if (
                    not cv
                    or not fact.get("excerpt")
                    or fact["excerpt"] not in cv[0]["text"]
                    or fact["text"] != fact["excerpt"]
                ):
                    raise ValueError(
                        "Verified fact must quote the selected CV exactly; use self-reported for manually approved wording"
                    )
                if not set(fact.get("skills", [])) <= set(skills_in(fact["excerpt"])):
                    raise ValueError("Verified skills must be present in the exact CV quote")
        store.set("profile", current)
        return {"ok": True}

    @app.post("/api/preferences")
    async def preferences(request: Request):
        body = await request.json()
        current = store.get("preferences")
        if not set(body) <= set(current):
            raise ValueError("Unsupported preference")
        current.update(body)
        if (
            not 60 <= int(current["poll_seconds"]) <= 86400
            or not 1 <= int(current["history_limit"]) <= 200
            or not 300 <= int(current["notification_seconds"]) <= 86400
            or not 0 <= float(current["minimum_score"]) <= 100
            or current["ai_mode"] not in ("basic", "local")
        ):
            raise ValueError("Preferences exceed supported bounds")
        store.set("preferences", current)
        return {"ok": True}

    @app.post("/api/applications")
    async def applications(request: Request):
        body = await request.json()
        job_id = int(body.pop("job_id"))
        confirmed = bool(body.pop("confirmed", False))
        if not store.job(job_id):
            raise ValueError("Vacancy not found")
        if body.get("letter_id") and not store.rows(
            "SELECT id FROM letters WHERE id=? AND job_id=?", (body["letter_id"], job_id)
        ):
            raise ValueError("Linked letter must belong to this vacancy")
        if body.get("cv_id") and not store.rows("SELECT id FROM cvs WHERE id=?", (body["cv_id"],)):
            raise ValueError("CV version not found")
        for key in ("notes", "recruiter", "rejection_reason"):
            if body.get(key) is not None and (not isinstance(body[key], str) or len(body[key]) > 15000):
                raise ValueError("Application text exceeds supported bounds")
        for key in ("applied_at", "interview_at", "followup_at", "observed_at"):
            if body.get(key):
                date = datetime.fromisoformat(body[key])
                if date.tzinfo is None:
                    raise ValueError("Dates must include a timezone")
        return {"id": store.save_application(job_id, body, confirmed)}

    @app.post("/api/feedback")
    async def feedback(request: Request):
        body = await request.json()
        job = store.job(int(body["job_id"]))
        if not job or type(body.get("relevant")) is not bool:
            raise ValueError("Choose a vacancy and a binary relevance label")
        with store.connect() as db:
            db.execute(
                "INSERT INTO feedback VALUES(?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET relevant=excluded.relevant,score=excluded.score,at=excluded.at",
                (job["id"], int(body["relevant"]), job["matching"]["score"], now()),
            )
        return {"ok": True}

    @app.post("/api/effort")
    async def effort(request: Request):
        body = await request.json()
        week = str(body.get("week", ""))
        if not re.fullmatch(r"\d{4}-W(?:0[1-9]|[1-4]\d|5[0-3])", week) or body.get("phase") not in (
            "baseline",
            "jobflow",
        ):
            raise ValueError("Choose an ISO week and measurement phase")
        entry = {"week": week, "phase": body["phase"], "at": now()}
        for key in ("search_minutes", "preparation_minutes", "qualified_applications"):
            value = body.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 10000:
                raise ValueError("Effort measurements must be finite, nonnegative values")
            entry[key] = value
        entries = store.get("effort_logs", [])
        entries = [e for e in entries if (e["week"], e["phase"]) != (week, entry["phase"])]
        store.set("effort_logs", (entries + [entry])[-200:])
        return {"ok": True}

    @app.post("/api/cvs")
    async def upload_cv(file: UploadFile = File(...), label: str = Form("CV")):
        try:
            content = await file.read(10 * 1024 * 1024 + 1)
            return import_cv(store, data_dir, file.filename or "", content, label)
        except ValueError:
            raise
        except Exception:
            raise ValueError("This CV could not be read safely. Choose a text PDF or valid DOCX.") from None

    @app.post("/api/letters")
    async def letters(request: Request):
        body = await request.json()
        return await draft_letter(
            store,
            int(body["job_id"]),
            body.get("cv_id"),
            body.get("language", "en"),
            body.get("style", "Professional"),
        )

    @app.patch("/api/letters/{letter_id}")
    async def edit_letter(letter_id: int, request: Request):
        body = await request.json()
        text = str(body.get("text", ""))
        if not text or len(text) > 15000:
            raise ValueError("Letter must contain 1–15,000 characters")
        original = store.rows("SELECT original_text FROM letters WHERE id=?", (letter_id,))
        if not original:
            raise HTTPException(404, "Letter not found")
        verified = text == original[0]["original_text"]
        with store.connect() as db:
            version = db.execute(
                "INSERT INTO letters(job_id,cv_id,text,original_text,evidence,language,style,verified,created_at) SELECT job_id,cv_id,?,original_text,evidence,language,style,?,? FROM letters WHERE id=?",
                (text, int(verified), now(), letter_id),
            ).lastrowid
        return {
            "id": version,
            "verified": verified,
            "warning": None
            if verified
            else "Edited text requires manual factual review; automatic claim support is no longer certified.",
        }

    @app.post("/api/tailor")
    async def tailor(request: Request):
        body = await request.json()
        return tailored_cv(store, int(body["job_id"]), body.get("cv_id"))

    @app.get("/api/cvs/{cv_id}/export/{format}")
    async def cv_export(cv_id: int, format: str):
        rows = store.rows("SELECT text FROM cvs WHERE id=?", (cv_id,))
        if not rows:
            raise HTTPException(404, "CV not found")
        blob = export_cv(rows[0]["text"], format)
        return Response(
            blob,
            media_type="application/pdf"
            if format == "pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="jobflow-cv-{cv_id}.{format}"'},
        )

    @app.post("/api/notify")
    async def notifications():
        return {"state": "Test mode · external delivery disabled"} if testing else await notify(store)

    @app.get("/api/backup")
    async def backup():
        path = data_dir / "backup.sqlite"
        store.backup(path)
        return FileResponse(
            path, filename="jobflow-private-backup.sqlite", media_type="application/octet-stream"
        )

    @app.post("/api/restore")
    async def restore(file: UploadFile = File(...)):
        if monitor.client and monitor.client.is_connected():
            raise ValueError("Stop the Telegram connection before restoring a backup")
        content = await file.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024 or not content.startswith(b"SQLite format 3\x00"):
            raise ValueError("Choose a SQLite backup under 10 MB")
        import sqlite3

        temp = data_dir / "restore.tmp"
        temp.write_bytes(content)
        try:
            with closing(sqlite3.connect(temp)) as source:
                if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Backup integrity check failed")
                tables = {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if (
                    not {
                        "sources",
                        "jobs",
                        "applications",
                        "settings",
                        "messages",
                        "status_events",
                        "cvs",
                        "letters",
                        "feedback",
                        "outbox",
                    }
                    <= tables
                ):
                    raise ValueError("Not a JobFlow backup")
                if source.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type IN('view','trigger')"
                ).fetchone()[0]:
                    raise ValueError("Backups containing views or triggers are not accepted")
                with store.connect() as current:
                    for table in tables:
                        if table == "sqlite_sequence":
                            continue
                        expected = [
                            tuple(r)[1:3] for r in current.execute("PRAGMA table_info(" + table + ")")
                        ]
                        actual = [tuple(r)[1:3] for r in source.execute("PRAGMA table_info(" + table + ")")]
                        if not expected or expected != actual:
                            raise ValueError("Backup schema does not match this JobFlow version")
                if source.execute("PRAGMA foreign_key_check").fetchall():
                    raise ValueError("Backup contains broken references")
                # Uploaded databases never supply arbitrary filesystem paths to the application.
                source.execute("UPDATE cvs SET file_path=NULL")
                source.execute("UPDATE outbox SET status='delivery_unknown' WHERE status='sending'")
                source.commit()
                with store.connect() as destination:
                    source.backup(destination)
            return {
                "ok": True,
                "note": "Restored data; original binary CV files are not included in a database backup.",
            }
        finally:
            temp.unlink(missing_ok=True)

    @app.post("/api/delete-data")
    async def delete_data(request: Request):
        body = await request.json()
        if body.get("confirmation") != "DELETE MY LOCAL DATA":
            raise ValueError("Type DELETE MY LOCAL DATA to confirm")
        await monitor.stop()
        with store.connect() as db:
            for table in (
                "status_events",
                "feedback",
                "outbox",
                "applications",
                "letters",
                "cvs",
                "messages",
                "jobs",
                "sources",
                "settings",
            ):
                db.execute("DELETE FROM " + table)
        for directory in (data_dir / "cvs",):
            if directory.exists():
                for path in directory.iterdir():
                    if path.is_file():
                        path.unlink()
        for pattern in ("telegram.session*", "backup.sqlite", "restore.tmp"):
            for path in data_dir.glob(pattern):
                if path.is_file():
                    path.unlink()
        sessions.clear()
        return {
            "ok": True,
            "note": "Data and local session removed. Restart JobFlow to initialize an empty workspace. Downloaded backups require separate deletion.",
        }

    @app.get("/")
    async def home():
        html = (
            (ROOT / "web/index.html")
            .read_text(encoding="utf-8")
            .replace('content="demo"', 'content="private"')
        )
        return HTMLResponse(html)

    @app.get("/case-study.html")
    async def case_study():
        return FileResponse(ROOT / "web/case-study.html", media_type="text/html")

    @app.get("/case-study.ru.html")
    async def case_study_ru():
        return FileResponse(ROOT / "web/case-study.ru.html", media_type="text/html")

    app.mount("/assets", StaticFiles(directory=ROOT / "web/assets"), name="assets")
    return app


def qa_app():
    return create_app(ROOT / "../../work/jobflow-qa", bootstrap="synthetic-test-launch", testing=True)
