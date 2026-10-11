"""Allowlisted synthetic-only Pages package. Never reads private/."""

import json
import shutil
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jobflow.matching import default_profile
from jobflow.storage import Store, dumps

ROOT = Path(__file__).resolve().parent.parent


def seed(store):
    profile = default_profile()
    profile.update(
        name="Avery Chen · fictional candidate",
        years_experience=2,
        languages={"English": "C1"},
        authorized_countries=["UAE"],
        salary_min=10000,
        salary_currency="AED",
        salary_period="month",
    )
    facts = [
        (
            "I built SQL analyses of signup funnels and retention cohorts for a fictional SaaS project.",
            ["SQL", "Product Analytics", "Statistics"],
        ),
        (
            "I organized product discovery and wrote acceptance criteria for a fictional API integration.",
            ["Discovery", "API", "Business Analysis", "Product Management"],
        ),
        (
            "I conducted usability research and prototyped interface concepts in a fictional portfolio exercise.",
            ["UX Research", "Figma"],
        ),
    ]
    profile["facts"] = [
        {
            "id": f"fictional-fact-{i}",
            "text": text,
            "skills": skills,
            "status": "self_reported",
            "approved": True,
            "cv_id": None,
            "excerpt": None,
        }
        for i, (text, skills) in enumerate(facts, 1)
    ]
    store.set("profile", profile)
    with store.connect() as db:
        db.execute("DELETE FROM sources")
        for name in ("demo_product_community", "demo_analytics_roles", "demo_remote_board"):
            db.execute(
                "INSERT INTO sources(username,enabled,verified) VALUES(?,1,'fictional demo source')", (name,)
            )
        db.execute(
            "INSERT INTO cvs(label,text,created_at) VALUES(?,?,?)",
            (
                "Fictional analyst CV",
                "Avery Chen · fictional candidate\n\n" + "\n".join(t for t, _ in facts),
                "2026-10-01T09:00:00+00:00",
            ),
        )
    roles = [
        "Product Analyst",
        "Business Analyst",
        "Associate Product Manager",
        "AI Product Manager",
        "UX Researcher",
        "Product Manager",
        "Senior Product Manager",
        "System Analyst",
    ]
    companies = [
        "Northstar Sandbox",
        "Signalpath Fictional",
        "Atlas Demo Labs",
        "Orbit Example Studio",
        "Maple Sample Systems",
        "Beacon Fictional Finance",
    ]
    skills = [
        "SQL, Product Analytics, Statistics",
        "SQL, Business Analysis, API",
        "Product Management, Discovery, API",
        "Product Management, Machine Learning, Python",
        "UX Research, Figma",
        "Product Management, Agile",
        "Product Management, SQL",
        "Business Analysis, API",
    ]
    base = datetime(2026, 10, 1, 9, tzinfo=UTC)
    for i in range(24):
        role = roles[i % len(roles)]
        country = ["Dubai, UAE", "International remote", "Moscow, Russia", "Berlin, Germany"][i % 4]
        text = (
            f"Vacancy: {role}\nCompany: {companies[i % 6]}\nLocation: {country}\n{'Remote worldwide' if i % 4 in (1, 2) else 'Hybrid'}\nRequirements: {skills[i % 8]}\n{'8+ years of experience' if 'Senior' in role else '2 years of experience'}\nEnglish C1\n"
            + (
                "Salary: 12000–18000 AED per month\nVisa sponsorship and relocation available\n"
                if i % 4 == 0
                else ""
            )
            + f"Apply: https://example.com/fictional-job-{i + 1}\nThis entire vacancy is synthetic demonstration data."
        )
        result = store.ingest(
            i % 3 + 1,
            i + 1,
            text,
            (base + timedelta(hours=i)).isoformat(),
            f"https://example.com/fictional-source/post-{i + 1}",
        )
        with store.connect() as db:
            db.execute(
                "UPDATE jobs SET first_discovered_at=? WHERE id=?",
                ((base + timedelta(hours=i, minutes=15)).isoformat(), result["job_id"]),
            )
    for i, status in [
        (1, "Interview"),
        (2, "Applied"),
        (3, "Saved"),
        (4, "Preparing"),
        (5, "Rejected"),
        (6, "Recruiter Screening"),
    ]:
        store.save_application(i, {"status": "Saved", "cv_id": 1, "observed_at": "2026-10-02T09:00:00+00:00"})
        if status not in ("Saved", "Preparing"):
            store.save_application(
                i,
                {
                    "status": "Applied",
                    "applied_at": "2026-10-03T09:00:00+00:00",
                    "observed_at": "2026-10-03T09:00:00+00:00",
                },
                True,
            )
        if status not in ("Saved", "Applied"):
            store.save_application(
                i,
                {
                    "status": status,
                    "observed_at": "2026-10-06T09:00:00+00:00",
                    "followup_at": "2026-10-13T09:00:00+00:00" if status == "Applied" else None,
                    "interview_at": "2026-10-14T10:00:00+00:00" if status == "Interview" else None,
                    "notes": "Fictional application history for demonstration only.",
                },
            )


def build():
    with tempfile.TemporaryDirectory() as temporary:
        store = Store(Path(temporary) / "synthetic.sqlite")
        seed(store)
        state = {
            "mode": "demo",
            "synthetic": True,
            "profile": store.get("profile"),
            "preferences": store.get("preferences"),
            "jobs": store.jobs(),
            "sources": store.rows("SELECT * FROM sources"),
            "cvs": store.rows("SELECT id,label,text,created_at,parent_id FROM cvs"),
            "letters": [],
            "applications": store.rows("SELECT * FROM applications"),
            "events": store.rows("SELECT * FROM status_events"),
            "analytics": store.analytics(),
            "outbox": [],
            "feedback": [],
            "telegram": "Public sandbox · disabled",
        }
        (ROOT / "web/assets/demo-data.json").write_text(dumps(state) + "\n", encoding="utf-8")
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    for name in ("index.html", "case-study.html"):
        if (ROOT / "web" / name).exists():
            shutil.copy2(ROOT / "web" / name, dist / name)
    shutil.copytree(ROOT / "web/assets", dist / "assets", dirs_exist_ok=True)
    (dist / ".nojekyll").write_text("", encoding="utf-8")
    allowed = {
        "index.html",
        "case-study.html",
        ".nojekyll",
        "assets/app.js",
        "assets/styles.css",
        "assets/demo-data.json",
    }
    assert {p.relative_to(dist).as_posix() for p in dist.rglob("*") if p.is_file()} <= allowed
    assert json.loads((dist / "assets/demo-data.json").read_text(encoding="utf-8"))["synthetic"] is True
    print(
        "Built public demo from an explicit synthetic seed and allowlisted web assets. No private input read."
    )


if __name__ == "__main__":
    build()
