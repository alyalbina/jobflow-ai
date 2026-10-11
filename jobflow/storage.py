"""Transactional persistence, source/message identity and immutable application history."""

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .matching import default_profile, match
from .parsing import canonical_hash, parse

STATUSES = [
    "Discovered",
    "Saved",
    "Preparing",
    "Applied",
    "Recruiter Screening",
    "Interview",
    "Test Assignment",
    "Offer",
    "Rejected",
    "Withdrawn",
    "No Response",
]
CHANNELS = [
    "revacancy_global",
    "job_web3",
    "revacancy",
    "foranalysts",
    "remotegeekjob",
    "JobOfferInside",
    "zarubezhom_jobs",
    "forproducts",
    "evacuatejobs",
    "montenegro_it_jobs",
    "talentmove_channel",
    "digitalclubjobs",
    "mediajobs_ru",
    "cryptoheadhunter",
    "workingincrypto",
    "careers_crypto",
    "opento_crypto",
    "web30job",
    "cryptovakansii",
    "iGaming_work",
    "rusukrjobs",
    "remote_jobs_relocate",
]


def now():
    return datetime.now(UTC).isoformat()


def dumps(value):
    return json.dumps(value, ensure_ascii=False)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,channel_id INTEGER,cursor INTEGER NOT NULL DEFAULT 0,
                verified TEXT NOT NULL DEFAULT 'unchecked',last_sync TEXT,error TEXT,next_retry TEXT);
            CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,content_hash TEXT UNIQUE NOT NULL,
                data TEXT NOT NULL,original_text TEXT NOT NULL,published_at TEXT NOT NULL,
                source_id INTEGER NOT NULL REFERENCES sources(id),original_url TEXT,
                manual_fields TEXT NOT NULL DEFAULT '{}',unavailable INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL,
                first_discovered_at TEXT);
            CREATE TABLE IF NOT EXISTS messages(source_id INTEGER REFERENCES sources(id),message_id INTEGER,
                text TEXT NOT NULL,published_at TEXT NOT NULL,content_hash TEXT NOT NULL,
                job_id INTEGER REFERENCES jobs(id),deleted INTEGER NOT NULL DEFAULT 0,edited_at TEXT,
                PRIMARY KEY(source_id,message_id));
            CREATE INDEX IF NOT EXISTS messages_job ON messages(job_id);
            CREATE TABLE IF NOT EXISTS cvs(id INTEGER PRIMARY KEY,label TEXT NOT NULL,text TEXT NOT NULL,
                file_path TEXT,created_at TEXT NOT NULL,parent_id INTEGER REFERENCES cvs(id));
            CREATE TABLE IF NOT EXISTS letters(id INTEGER PRIMARY KEY,job_id INTEGER REFERENCES jobs(id),
                cv_id INTEGER REFERENCES cvs(id),text TEXT NOT NULL,original_text TEXT NOT NULL,
                evidence TEXT NOT NULL,language TEXT NOT NULL,style TEXT NOT NULL,
                verified INTEGER NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS applications(id INTEGER PRIMARY KEY,job_id INTEGER UNIQUE REFERENCES jobs(id),
                status TEXT NOT NULL,applied_at TEXT,interview_at TEXT,followup_at TEXT,recruiter TEXT,
                notes TEXT NOT NULL DEFAULT '',rejection_reason TEXT,cv_id INTEGER REFERENCES cvs(id),
                letter_id INTEGER REFERENCES letters(id),created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS status_events(id INTEGER PRIMARY KEY,
                application_id INTEGER NOT NULL REFERENCES applications(id),from_status TEXT,to_status TEXT NOT NULL,
                at TEXT NOT NULL,manual_confirmation INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS feedback(job_id INTEGER PRIMARY KEY REFERENCES jobs(id),
                relevant INTEGER NOT NULL CHECK(relevant IN(0,1)),score REAL NOT NULL,at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY,dedupe_key TEXT UNIQUE NOT NULL,
                kind TEXT NOT NULL,body TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'queued',
                created_at TEXT NOT NULL,sent_at TEXT,error TEXT);
            """)
            if "first_discovered_at" not in {r["name"] for r in db.execute("PRAGMA table_info(jobs)")}:
                db.execute("ALTER TABLE jobs ADD COLUMN first_discovered_at TEXT")
            for username in CHANNELS:
                db.execute("INSERT OR IGNORE INTO sources(username) VALUES(?)", (username,))
        if self.get("profile") is None:
            self.set("profile", default_profile())
        if self.get("preferences") is None:
            self.set(
                "preferences",
                {
                    "poll_seconds": 900,
                    "history_limit": 50,
                    "notifications": False,
                    "notification_seconds": 3600,
                    "minimum_score": 75,
                    "ai_mode": "basic",
                },
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, key, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.connect() as db:
            db.execute(
                "INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, dumps(value)),
            )

    def rows(self, sql, args=()):
        with self.connect() as db:
            return [dict(r) for r in db.execute(sql, args)]

    def source_update(self, source_id, **fields):
        assert set(fields) <= {
            "enabled",
            "channel_id",
            "cursor",
            "verified",
            "last_sync",
            "error",
            "next_retry",
        }
        with self.connect() as db:
            db.execute(
                "UPDATE sources SET " + ",".join(k + "=?" for k in fields) + " WHERE id=?",
                (*fields.values(), source_id),
            )

    def ingest(self, source_id, message_id, text, published_at, original_url=None, advance=True):
        digest = canonical_hash(text)
        data = parse(text)
        with self.connect() as db:
            old = db.execute(
                "SELECT * FROM messages WHERE source_id=? AND message_id=?", (source_id, message_id)
            ).fetchone()
            if old and old["content_hash"] == digest and old["text"] == text and not old["deleted"]:
                if advance:
                    db.execute("UPDATE sources SET cursor=MAX(cursor,?) WHERE id=?", (message_id, source_id))
                return {"duplicate": True, "job_id": old["job_id"]}
            existing = db.execute("SELECT id FROM jobs WHERE content_hash=?", (digest,)).fetchone()
            job_id = existing["id"] if existing else None
            cross_duplicate = existing is not None and old is None
            if data["classification"] == "vacancy":
                if not existing:
                    shared = (
                        db.execute(
                            "SELECT COUNT(*) FROM messages WHERE job_id=? AND deleted=0", (old["job_id"],)
                        ).fetchone()[0]
                        if old and old["job_id"]
                        else 0
                    )
                    if old and old["job_id"] and shared == 1:
                        job_id = old["job_id"]
                        db.execute(
                            "UPDATE jobs SET content_hash=?,data=?,original_text=?,unavailable=0,updated_at=? WHERE id=?",
                            (digest, dumps(data), text, now(), job_id),
                        )
                    else:
                        result = db.execute(
                            "INSERT INTO jobs(content_hash,data,original_text,published_at,source_id,original_url,updated_at,first_discovered_at) VALUES(?,?,?,?,?,?,?,?)",
                            (digest, dumps(data), text, published_at, source_id, original_url, now(), now()),
                        )
                        job_id = result.lastrowid
                else:
                    db.execute("UPDATE jobs SET unavailable=0 WHERE id=?", (job_id,))
            else:
                job_id = None
            db.execute(
                """INSERT INTO messages VALUES(?,?,?,?,?,?,0,?) ON CONFLICT(source_id,message_id)
                DO UPDATE SET text=excluded.text,published_at=excluded.published_at,content_hash=excluded.content_hash,
                job_id=excluded.job_id,deleted=0,edited_at=excluded.edited_at""",
                (source_id, message_id, text, published_at, digest, job_id, now() if old else None),
            )
            if old and old["job_id"] != job_id:
                db.execute(
                    "UPDATE jobs SET unavailable=1 WHERE id=? AND NOT EXISTS(SELECT 1 FROM messages WHERE job_id=? AND deleted=0)",
                    (old["job_id"], old["job_id"]),
                )
            if advance:
                db.execute("UPDATE sources SET cursor=MAX(cursor,?) WHERE id=?", (message_id, source_id))
        return {"duplicate": cross_duplicate, "job_id": job_id, "classification": data["classification"]}

    def delete_messages(self, source_id, ids):
        with self.connect() as db:
            for mid in ids:
                row = db.execute(
                    "SELECT job_id FROM messages WHERE source_id=? AND message_id=?", (source_id, mid)
                ).fetchone()
                db.execute(
                    "UPDATE messages SET deleted=1 WHERE source_id=? AND message_id=?", (source_id, mid)
                )
                if row and row["job_id"]:
                    db.execute(
                        "UPDATE jobs SET unavailable=1 WHERE id=? AND NOT EXISTS(SELECT 1 FROM messages WHERE job_id=? AND deleted=0)",
                        (row["job_id"], row["job_id"]),
                    )

    def jobs(self):
        profile = self.get("profile")
        result = []
        for row in self.rows(
            "SELECT j.*,s.username source FROM jobs j JOIN sources s ON s.id=j.source_id ORDER BY published_at DESC,id DESC"
        ):
            parsed = json.loads(row.pop("data"))
            parsed.update(json.loads(row.pop("manual_fields")))
            row.update(parsed)
            row["matching"] = match(row, profile)
            result.append(row)
        return result

    def job(self, job_id):
        return next((j for j in self.jobs() if j["id"] == job_id), None)

    def save_application(self, job_id, fields, confirmed=False):
        if fields.get("status") not in STATUSES:
            raise ValueError("Unknown application status")
        if fields["status"] == "Applied" and not confirmed:
            raise ValueError("Manually confirm that you actually submitted the application")
        with self.connect() as db:
            old = db.execute("SELECT * FROM applications WHERE job_id=?", (job_id,)).fetchone()
            old_status = old["status"] if old else None
            data = {
                k: v
                for k, v in fields.items()
                if k
                in (
                    "status",
                    "applied_at",
                    "interview_at",
                    "followup_at",
                    "recruiter",
                    "notes",
                    "rejection_reason",
                    "cv_id",
                    "letter_id",
                )
            }
            timestamp = now()
            if (
                data["status"] == "Applied"
                and not data.get("applied_at")
                and (not old or not old["applied_at"])
            ):
                data["applied_at"] = timestamp
            if old:
                app_id = old["id"]
                db.execute(
                    "UPDATE applications SET "
                    + ",".join(k + "=?" for k in data)
                    + ",updated_at=? WHERE id=?",
                    (*data.values(), timestamp, app_id),
                )
            else:
                data.update(job_id=job_id, created_at=timestamp, updated_at=timestamp)
                app_id = db.execute(
                    "INSERT INTO applications("
                    + ",".join(data)
                    + ") VALUES("
                    + ",".join("?" for _ in data)
                    + ")",
                    tuple(data.values()),
                ).lastrowid
            if old_status != fields["status"]:
                db.execute(
                    "INSERT INTO status_events(application_id,from_status,to_status,at,manual_confirmation) VALUES(?,?,?,?,?)",
                    (
                        app_id,
                        old_status,
                        fields["status"],
                        fields.get("observed_at") or timestamp,
                        int(confirmed),
                    ),
                )
        return app_id

    def backup(self, target):
        with self.connect() as db, closing(sqlite3.connect(target)) as dest:
            db.backup(dest)

    def enqueue(self, key, kind, body):
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO outbox(dedupe_key,kind,body,created_at) VALUES(?,?,?,?)",
                (key, kind, body, now()),
            )

    def analytics(self):
        jobs = self.jobs()
        apps = self.rows("SELECT * FROM applications")
        events = self.rows("SELECT * FROM status_events ORDER BY at,id")
        stages = {
            status: {e["application_id"] for e in events if e["to_status"] == status} for status in STATUSES
        }

        def rate(a, b):
            den = stages[a]
            return len(den & stages[b]) / len(den) if den else None

        applied = stages["Applied"]
        responded = set().union(
            *(stages[s] for s in ("Recruiter Screening", "Interview", "Test Assignment", "Offer", "Rejected"))
        )
        times = []
        for app in apps:
            if app["id"] not in applied or not app["applied_at"]:
                continue
            applied_date = datetime.fromisoformat(app["applied_at"])
            responses = [
                datetime.fromisoformat(e["at"])
                for e in events
                if e["application_id"] == app["id"]
                and e["to_status"]
                in ("Recruiter Screening", "Interview", "Test Assignment", "Offer", "Rejected")
                and datetime.fromisoformat(e["at"]) >= applied_date
            ]
            if responses:
                times.append((min(responses) - applied_date).total_seconds() / 86400)
        from collections import Counter

        messages = self.rows("SELECT * FROM messages")
        live = [m for m in messages if not m["deleted"]]
        duplicates = len(live) - len({m["content_hash"] for m in live})
        feedback = self.rows("SELECT * FROM feedback")
        labelled = {x["job_id"]: x for x in feedback}
        ranked = sorted(
            [j for j in jobs if not j["unavailable"]], key=lambda j: j["matching"]["score"], reverse=True
        )
        top = ranked[:10]
        p10 = (
            sum(labelled[j["id"]]["relevant"] for j in top) / len(top)
            if top and all(j["id"] in labelled for j in top)
            else None
        )
        predicted = {j["id"] for j in ranked if j["matching"]["action"] == "Apply"}
        positives = {f["job_id"] for f in feedback if f["relevant"]}
        full = bool(ranked) and len(labelled) == len(ranked) and set(labelled) == {j["id"] for j in ranked}
        job_by_id = {j["id"]: j for j in jobs}
        cv_names = {c["id"]: c["label"] for c in self.rows("SELECT id,label FROM cvs")}
        comparisons = {}
        for dimension in ("source", "country", "role", "cv"):
            groups = {}
            for app in apps:
                job = job_by_id.get(app["job_id"], {})
                key = (
                    (
                        f"CV {app['cv_id']} · {cv_names[app['cv_id']]}"
                        if app["cv_id"] in cv_names
                        else "Not linked"
                    )
                    if dimension == "cv"
                    else job.get(dimension) or "Unknown"
                )
                group = groups.setdefault(
                    key, {"tracked": 0, "applied": 0, "responses": 0, "interviews": 0, "offers": 0}
                )
                group["tracked"] += 1
                if app["id"] in applied:
                    group["applied"] += 1
                    group["responses"] += int(app["id"] in responded)
                    group["interviews"] += int(app["id"] in stages["Interview"])
                    group["offers"] += int(app["id"] in stages["Offer"])
            comparisons[dimension] = groups
        weekly = {}
        for label in feedback:
            week = datetime.fromisoformat(label["at"]).strftime("%G-W%V")
            group = weekly.setdefault(
                week, {"labelled": 0, "relevant": 0, "score_75plus": 0, "relevant_75plus": 0}
            )
            group["labelled"] += 1
            group["relevant"] += label["relevant"]
            if label["score"] >= 75:
                group["score_75plus"] += 1
                group["relevant_75plus"] += label["relevant"]
        geo_mismatch = sum(
            any(
                "location" in x.lower() or "authorization" in x.lower() or "relocation" in x.lower()
                for x in j["matching"]["hard_filters"]
            )
            for j in ranked
        )
        delays = []
        application_delays = []
        for app in apps:
            discovered = job_by_id.get(app["job_id"], {}).get("first_discovered_at")
            if app["id"] in applied and app["applied_at"] and discovered:
                try:
                    hours = (
                        datetime.fromisoformat(app["applied_at"]) - datetime.fromisoformat(discovered)
                    ).total_seconds() / 3600
                    if hours >= 0:
                        application_delays.append(hours)
                except (ValueError, TypeError):
                    pass
        for job in ranked:
            if job.get("first_discovered_at"):
                try:
                    delay = (
                        datetime.fromisoformat(job["first_discovered_at"])
                        - datetime.fromisoformat(job["published_at"])
                    ).total_seconds() / 3600
                    if delay >= 0:
                        delays.append(delay)
                except (ValueError, TypeError):
                    pass
        return {
            "messages": len(messages),
            "valid_vacancies": len(ranked),
            "duplicate_rate": duplicates / len(live) if live else None,
            "relevant_vacancies": len(predicted),
            "by_source": dict(Counter(j["source"] for j in ranked)),
            "by_country": dict(Counter(j.get("country") or "Unknown" for j in ranked)),
            "by_role": dict(Counter(j.get("role") or "Unknown" for j in ranked)),
            "statuses": {k: len(v) for k, v in stages.items()},
            "current_statuses": dict(Counter(a["status"] for a in apps)),
            "funnel": {
                "Saved → Applied": rate("Saved", "Applied"),
                "Applied → Screening": rate("Applied", "Recruiter Screening"),
                "Screening → Interview": rate("Recruiter Screening", "Interview"),
                "Interview → Offer": rate("Interview", "Offer"),
            },
            "response_rate": len(applied & responded) / len(applied) if applied else None,
            "rejection_rate": len(applied & stages["Rejected"]) / len(applied) if applied else None,
            "response_days_mean": sum(times) / len(times) if times else None,
            "response_sample": len(times),
            "precision_at_10": p10,
            "labelled_jobs": len(feedback),
            "recall": len(positives & predicted) / len(positives) if full and positives else None,
            "false_positives": len(predicted & {f["job_id"] for f in feedback if not f["relevant"]}),
            "false_negatives": len(positives - predicted),
            "fully_labelled": full,
            "manual_corrections": sum(
                bool(json.loads(r["manual_fields"])) for r in self.rows("SELECT manual_fields FROM jobs")
            ),
            "comparisons": comparisons,
            "quality_weeks": weekly,
            "geo_mismatch": geo_mismatch,
            "discovery_hours_mean": sum(delays) / len(delays) if delays else None,
            "discovery_sample": len(delays),
            "discovery_to_application_hours_mean": sum(application_delays) / len(application_delays)
            if application_delays
            else None,
            "discovery_to_application_sample": len(application_delays),
            "effort_logs": self.get("effort_logs", []),
            "limits": "Descriptive, small-sample associations. Stage skips are not inferred. Unlabelled jobs are not negatives.",
        }
