"""Reject private artifacts or credential patterns from tracked/public files."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = [
    re.compile(r"\b\d{8,12}:AA[A-Za-z0-9_-]{25,}\b"),
    re.compile(r"\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_]{20,}\b"),
    re.compile(r"TELEGRAM_API_HASH\s*=\s*[a-fA-F0-9]{32}\b"),
]


def check(paths):
    for path in paths:
        relative = path.relative_to(ROOT)
        if (
            any(part in ("private", ".venv", "__pycache__") for part in relative.parts)
            or path.suffix in (".session", ".sqlite", ".db", ".pyc")
            or path.name == ".env"
        ):
            raise ValueError("Private artifact in public package: " + str(relative))
        if path.is_file() and path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".zip"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(pattern.search(text) for pattern in PATTERNS):
                raise ValueError("Credential pattern detected in " + str(relative))
    return True


def main():
    result = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False)
    paths = (
        [ROOT / p for p in result.stdout.splitlines()]
        if result.returncode == 0 and result.stdout
        else [
            p
            for folder in ("jobflow", "scripts", "web", "tests", "docs", ".github")
            for p in (ROOT / folder).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        ]
    )
    check(paths)
    check([p for p in (ROOT / "dist").rglob("*") if p.is_file()])
    print(
        f"Public-boundary scan passed: {len(paths)} source files; private artifact and credential patterns absent."
    )


if __name__ == "__main__":
    main()
