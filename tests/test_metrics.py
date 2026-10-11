from jobflow.storage import Store, now


def test_cv_outcome_groups_use_distinct_version_ids(tmp_path):
    store = Store(tmp_path / "metrics.sqlite")
    with store.connect() as db:
        for i in (1, 2):
            db.execute(
                "INSERT INTO cvs(id,label,text,created_at) VALUES(?,?,?,?)",
                (i, "Same label", "Fictional evidence", now()),
            )
    for i in (1, 2):
        job = store.ingest(
            1, i, f"Vacancy: Product Analyst\nCompany: Fictional {i}\nRequirements: SQL", now()
        )["job_id"]
        store.save_application(job, {"status": "Applied", "cv_id": i}, confirmed=True)
    metrics = store.analytics()
    assert len(metrics["comparisons"]["cv"]) == 2
    assert all(g["applied"] == 1 for g in metrics["comparisons"]["cv"].values())
    assert "revacancy_global" in metrics["comparisons"]["source"]


def test_response_time_uses_applied_cohort_and_timezone_instants(tmp_path):
    store = Store(tmp_path / "metrics.sqlite")
    job = store.ingest(1, 1, "Vacancy: Product Analyst\nCompany: Fictional\nRequirements: SQL", now())[
        "job_id"
    ]
    store.save_application(
        job, {"status": "Applied", "applied_at": "2026-10-01T23:00:00-02:00"}, confirmed=True
    )
    store.save_application(job, {"status": "Interview", "observed_at": "2026-10-02T02:00:00+00:00"})
    other = store.ingest(
        1, 2, "Vacancy: Business Analyst\nCompany: Other Fictional\nRequirements: API", now()
    )["job_id"]
    store.save_application(
        other,
        {
            "status": "Interview",
            "applied_at": "2026-10-01T00:00:00+00:00",
            "observed_at": "2026-10-05T00:00:00+00:00",
        },
    )
    metrics = store.analytics()
    assert metrics["response_sample"] == 1
    assert abs(metrics["response_days_mean"] - 1 / 24) < 1e-9
