import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from telethon import errors
from telethon.tl.types import Channel

from jobflow.integrations import Monitor, notify
from jobflow.matching import default_profile, match
from jobflow.parsing import parse
from jobflow.storage import Store, now
from jobflow.studio import draft_letter, extract_cv, select_facts

TEXT = "Vacancy: Middle Product Analyst\nCompany: Example Fictional\nLocation: Dubai UAE\nHybrid\nRequirements: SQL, Statistics\n2 years experience\nEnglish C1\nSalary: 12000–18000 AED per month\nVisa sponsorship available\nApply: https://example.com/job"


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "private.sqlite")


def profile():
    p = default_profile()
    p.update(
        years_experience=2,
        languages={"English": "C1"},
        facts=[
            {
                "id": "sql-proof",
                "text": "I used SQL for a fictional portfolio analysis.",
                "skills": ["SQL", "Statistics"],
                "status": "self_reported",
                "approved": True,
            }
        ],
    )
    return p


def test_parse_explicit_fields_and_salary():
    p = parse(TEXT)
    assert p["classification"] == "vacancy"
    assert p["role"] == "Product Analyst" and p["country"] == "UAE"
    assert p["salary_min"] == 12000 and p["salary_max"] == 18000
    assert p["currency"] == "AED" and p["salary_period"] == "month"
    assert p["required_skills"] == ["SQL", "Statistics"]
    assert p["company"] == "Example Fictional"


def test_missing_fields_not_invented():
    p = parse("Vacancy: Product Manager\nRequirements: Discovery")
    for key in ("company", "country", "salary_min", "currency", "years_experience", "relocation"):
        assert p[key] is None


def test_explicit_industry_experience_and_country_only_restriction():
    job = parse(
        "Vacancy: Product Analyst\nRemote: UAE only\nRequirements: SQL\nExperience in FinTech required"
    )
    assert job["country_restricted"] and job["industry_requirement"] == "FinTech"
    result = match(job, profile())
    assert any("Industry experience" in gap for gap in result["gaps"])


def test_unknown_required_language_requires_review():
    p = profile()
    p["languages"] = {}
    result = match(parse(TEXT), p)
    assert result["action"] != "Apply" and not result["hard_filters"]
    assert "English proficiency is unknown" in result["unknowns"]


def test_supported_skill_is_not_mislabelled_as_inferred_only():
    p = profile()
    p["facts"].append(
        {
            "id": "proposal",
            "text": "An unchecked SQL proposal",
            "skills": ["SQL"],
            "status": "inferred",
            "approved": False,
        }
    )
    result = match(parse(TEXT), p)
    assert "Supported skill: SQL" in result["why"]
    assert not any("Inferred only" in reason for reason in result["unknowns"])


def test_unicode_pdf_export_roundtrips_actual_text():
    from io import BytesIO

    from pypdf import PdfReader

    from jobflow.studio import export_cv

    text = "Fictional candidate\nПодтверждённый опыт SQL\nAnalytical evidence"
    reader = PdfReader(BytesIO(export_cv(text, "pdf")))
    extracted = "\n".join(p.extract_text() for p in reader.pages)
    assert "Подтверждённый опыт SQL" in extracted and "Analytical evidence" in extracted


@pytest.mark.parametrize(
    "text,classification",
    [
        ("Product Analyst course webinar! Learn SQL", "advertisement"),
        ("Подборка вакансий Product Analyst https://example.com/a https://example.com/b", "roundup"),
        ("News: Telegram platform announces changes", "news"),
        ("Hello everyone!", "non_vacancy"),
        ("Вакансия: Бизнес-аналитик\nКомпания: Example\nТребования: SQL\nУдалённая работа", "vacancy"),
        ("Vacancy: Software Engineer\nRequirements: Python", "vacancy"),
    ],
)
def test_classification(text, classification):
    assert parse(text)["classification"] == classification


def test_required_vs_nice():
    p = parse("Vacancy: Product Analyst\nRequirements: SQL\nNice to have: Python\nWe offer: remote")
    assert p["required_skills"] == ["SQL"] and p["nice_skills"] == ["Python"]


def test_candidate_never_acquires_vacancy_skills():
    p = profile()
    j = parse(TEXT + "\nPython required")
    result = match(j, p)
    assert any("Python" in x for x in result["gaps"])
    assert "Python" not in p["facts"][0]["skills"]
    assert result["action"] == "Review"


def test_inferred_facts_not_used():
    p = profile()
    p["facts"][0]["status"] = "inferred"
    result = match(parse(TEXT), p)
    assert not result["evidence_ids"]
    assert any("SQL" in x for x in result["gaps"])


def test_unknown_authorization_is_not_confirmed_mismatch():
    job = parse(TEXT + "\nMust be resident in UAE")
    p = profile()
    r = match(job, p)
    assert not r["hard_filters"] and any("authorization" in x for x in r["unknowns"])
    p["authorized_countries"] = ["Russia"]
    assert match(job, p)["action"] == "Skip"


def test_senior_unknown_not_recommended():
    p = profile()
    p["years_experience"] = None
    result = match(parse(TEXT.replace("Middle", "Senior").replace("2 years", "8 years")), p)
    assert result["action"] == "Skip"
    assert not any("Confirmed experience" in x for x in result["hard_filters"])


def test_hard_language_and_role_filters():
    p = profile()
    p["languages"]["German"] = "none"
    assert match(parse(TEXT + "\nGerman C1 required"), p)["action"] == "Skip"
    assert match(parse("Vacancy: Software Engineer\nRequirements: Python"), p)["action"] == "Skip"


def test_dedup_edit_delete_and_cursor_transaction(store):
    first = store.ingest(1, 10, TEXT, now(), "https://example.com/a")
    repeat = store.ingest(1, 10, TEXT, now(), "https://example.com/a")
    cross = store.ingest(2, 20, TEXT, now(), "https://example.com/b")
    assert repeat["duplicate"] and cross["duplicate"]
    assert first["job_id"] == cross["job_id"] and len(store.jobs()) == 1
    edit = store.ingest(1, 10, TEXT.replace("12000", "14000"), now(), advance=False)
    assert edit["job_id"] != first["job_id"]
    assert len(store.jobs()) == 2
    store.delete_messages(1, [10])
    assert store.job(edit["job_id"])["unavailable"]
    assert not store.job(first["job_id"])["unavailable"]
    assert store.rows("SELECT cursor FROM sources WHERE id=1")[0]["cursor"] == 10


def test_failed_ingest_does_not_advance_cursor(store):
    with pytest.raises(__import__("sqlite3").IntegrityError):
        store.ingest(999, 100, TEXT, now())
    assert not store.jobs()


def test_single_message_edit_preserves_application_identity(store):
    job = store.ingest(1, 1, TEXT, now())["job_id"]
    app = store.save_application(job, {"status": "Saved"})
    edited = store.ingest(1, 1, TEXT + "\nNice to have: Python", now(), advance=False)
    assert edited["job_id"] == job
    assert store.rows("SELECT id FROM applications")[0]["id"] == app


def test_preparing_is_not_applied_and_history_is_durable(store):
    job = store.ingest(1, 1, TEXT, now())["job_id"]
    store.save_application(job, {"status": "Saved"})
    store.save_application(job, {"status": "Preparing"})
    with pytest.raises(ValueError):
        store.save_application(job, {"status": "Applied"})
    assert store.rows("SELECT applied_at FROM applications")[0]["applied_at"] is None
    store.save_application(job, {"status": "Applied"}, True)
    reopened = Store(store.path)
    assert len(reopened.rows("SELECT * FROM status_events")) == 3
    assert reopened.analytics()["funnel"]["Saved → Applied"] == 1
    assert reopened.analytics()["response_rate"] == 0


def test_empty_denominators_and_unlabelled_jobs(store):
    a = store.analytics()
    assert a["response_rate"] is None and a["precision_at_10"] is None
    store.ingest(1, 1, TEXT, now())
    assert store.analytics()["precision_at_10"] is None
    assert store.analytics()["recall"] is None


def test_backup_preserves_consistent_records(store, tmp_path):
    store.ingest(1, 1, TEXT, now())
    path = tmp_path / "backup.sqlite"
    store.backup(path)
    assert Store(path).jobs()[0]["original_text"] == TEXT


def test_grounded_letter_and_no_unapproved_claims(store):
    job = store.ingest(1, 1, TEXT, now())["job_id"]
    p = profile()
    p["facts"].append(
        {
            "id": "unsupported",
            "text": "I increased revenue by 500%.",
            "skills": ["Python"],
            "status": "inferred",
            "approved": False,
        }
    )
    store.set("profile", p)
    for language in ("en", "ru"):
        letter = asyncio.run(draft_letter(store, job, None, language, "Concise"))
        assert "500%" not in letter["text"]
        assert p["facts"][0]["text"] in letter["text"]
        assert letter["verified"]


def test_ollama_unsupported_ids_and_network_error_fallback():
    facts = profile()["facts"]
    job = {"required_skills": ["SQL"], "original_text": TEXT}
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, json={"response": '{"ids":["invented-fact"]}'})
    )
    selected, method, warning = asyncio.run(select_facts(facts, job, "synthetic-test-model", transport))
    assert selected == facts and method == "Basic fallback" and warning

    def failed(r):
        raise httpx.ConnectError("Offline")

    assert asyncio.run(select_facts(facts, job, "test", httpx.MockTransport(failed)))[1] == "Basic fallback"


def test_ollama_accepts_only_supported_selection():
    facts = profile()["facts"]
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"response": '{"ids":["sql-proof"]}'}))
    selected, method, warning = asyncio.run(select_facts(facts, {}, "test", transport))
    assert selected == facts and method.startswith("Local AI") and warning is None


def test_cv_rejects_unknown_format_and_unreadable_content():
    with pytest.raises(ValueError):
        extract_cv("cv.html", b"<script>alert(1)</script>")
    with pytest.raises(ValueError):
        extract_cv("cv.pdf", b"x" * (10 * 1024 * 1024 + 1))


class FakeClient:
    def __init__(self):
        self.batch = []
        self.requested = []
        self.fail = False

    async def get_entity(self, username):
        if self.fail:
            raise OSError("Offline")
        return Channel(id=42, title="Fictional", photo=None, date=datetime.now(UTC), broadcast=True)

    async def get_messages(self, entity, limit=None, ids=None):
        self.requested.append({"limit": limit, "ids": ids})
        return [next((m for m in self.batch if m.id == i), None) for i in ids] if ids else self.batch[-limit:]

    async def iter_messages(self, entity, **kwargs):
        self.requested.append(kwargs)
        for m in self.batch:
            if m.id > kwargs["min_id"]:
                yield m


def message(id, text=TEXT):
    return SimpleNamespace(id=id, raw_text=text, date=datetime.now(UTC))


def test_bounded_history_catchup_edit_delete_and_network_retry(store, tmp_path):
    monitor = Monitor(store, tmp_path)
    client = FakeClient()
    monitor.client = client
    client.batch = [message(1), message(2, TEXT + "\nAdditional info")]
    source = store.rows("SELECT * FROM sources WHERE id=1")[0]
    asyncio.run(monitor.sync_source(source))
    assert client.requested[0]["limit"] == 50
    assert store.rows("SELECT cursor FROM sources WHERE id=1")[0]["cursor"] == 2
    client.batch = [message(2, TEXT + "\nEdited"), message(3, TEXT + "\nNew vacancy")]
    source = store.rows("SELECT * FROM sources WHERE id=1")[0]
    asyncio.run(monitor.sync_source(source))
    assert any(r.get("min_id") == 2 and r["reverse"] for r in client.requested)
    assert store.rows("SELECT text FROM messages WHERE message_id=2")[0]["text"].endswith("Edited")
    assert store.rows("SELECT deleted FROM messages WHERE message_id=1")[0]["deleted"] == 1
    client.fail = True
    asyncio.run(monitor.sync_source(source))
    assert "Temporary" in store.rows("SELECT error FROM sources WHERE id=1")[0]["error"]
    assert store.rows("SELECT cursor FROM sources WHERE id=1")[0]["cursor"] == 3


def test_flood_wait_persists_retry_deadline(store, tmp_path):
    client = FakeClient()

    async def flood(username):
        raise errors.FloodWaitError(request=None, capture=120)

    client.get_entity = flood
    monitor = Monitor(store, tmp_path)
    monitor.client = client
    asyncio.run(monitor.sync_source(store.rows("SELECT * FROM sources WHERE id=1")[0]))
    row = store.rows("SELECT next_retry,error FROM sources WHERE id=1")[0]
    assert row["next_retry"] > now() and "120 seconds" in row["error"]


def test_notification_no_repeat_and_ambiguous_timeout(store, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "synthetic-not-a-real-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    prefs = store.get("preferences")
    prefs.update(notifications=True)
    store.set("preferences", prefs)
    store.enqueue("synthetic:1", "followup", "Fictional reminder")
    calls = []

    def delivered(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    assert asyncio.run(notify(store, httpx.MockTransport(delivered)))["state"] == "sent"
    asyncio.run(notify(store, httpx.MockTransport(delivered)))
    assert len(calls) == 1
    store.set("last_notification", None)
    store.enqueue("synthetic:2", "followup", "Second fictional reminder")

    def timeout(request):
        raise httpx.ReadTimeout("Ambiguous")

    assert asyncio.run(notify(store, httpx.MockTransport(timeout)))["state"] == "delivery_unknown"
    assert asyncio.run(notify(store, httpx.MockTransport(delivered)))["state"] == "Nothing due"


def test_public_builder_allowlist_excludes_private_data(tmp_path, monkeypatch):
    from scripts import build_demo

    (tmp_path / "web/assets").mkdir(parents=True)
    (tmp_path / "web/index.html").write_text("<h1>Fictional demo</h1>")
    (tmp_path / "web/assets/app.js").write_text('const mode="demo";')
    (tmp_path / "private").mkdir()
    marker = "PRIVATE-CV-CANARY-NOT-FOR-PUBLICATION"
    (tmp_path / "private/cv.txt").write_text(marker)
    (tmp_path / "private/telegram.session").write_bytes(marker.encode())
    monkeypatch.setattr(build_demo, "ROOT", tmp_path)
    build_demo.build()
    for path in (tmp_path / "dist").rglob("*"):
        if path.is_file():
            assert marker.encode() not in path.read_bytes()
            assert "private" not in path.relative_to(tmp_path / "dist").parts
    import json

    demo = json.loads((tmp_path / "dist/assets/demo-data.json").read_text(encoding="utf-8"))
    assert demo["synthetic"] and all("file_path" not in cv for cv in demo["cvs"])
