import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from jobflow.matching import match
from jobflow.storage import Store
from scripts.build_demo import seed


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"years_experience": None},
        {"languages": {}},
        {"authorized_countries": []},
        {"relocation_required": True},
        {"formats": ["on-site"]},
        {"salary_min": 30000},
        {"languages": {"English": "B1"}},
    ],
)
def test_public_matching_agrees_with_private_policy(tmp_path, changes):
    if not shutil.which("node"):
        pytest.skip("Node is required for the public scorer parity check")
    store = Store(tmp_path / "fictional.sqlite")
    seed(store)
    profile = store.get("profile")
    profile.update(changes)
    jobs = store.jobs()
    data = {"profile": profile, "jobs": copy.deepcopy(jobs)}
    result = subprocess.run(
        ["node", "scripts/check_demo.js"],
        input=json.dumps(data),
        text=True,
        capture_output=True,
        check=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    public = json.loads(result.stdout)
    for job, actual in zip(jobs, public, strict=True):
        expected = match(job, profile)
        assert actual["id"] == job["id"]
        assert actual["score"] == expected["score"]
        assert actual["action"] == expected["action"]
