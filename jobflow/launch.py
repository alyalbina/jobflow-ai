"""Owner-operated launcher; one-time fragment token is never logged or transmitted externally."""

import os
import secrets
import subprocess
import threading
import webbrowser
from pathlib import Path

import uvicorn

from .app import create_app


def main():
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    data = (root / "private").resolve()
    data.mkdir(exist_ok=True)
    if os.name == "nt":
        user = os.environ.get("USERNAME")
        if user:
            result = subprocess.run(
                ["icacls", str(data), "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F"], capture_output=True
            )
            if result.returncode:
                raise RuntimeError(
                    "Could not restrict private folder access. Review Windows permissions before using real CVs."
                )
    else:
        data.chmod(0o700)
    token = secrets.token_urlsafe(32)
    app = create_app(data, bootstrap=token)
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:8765/#bootstrap=" + token)).start()
    print("JobFlow is starting locally. Keep this window open; Ctrl+C stops monitoring.")
    uvicorn.run(app, host="127.0.0.1", port=8765, access_log=False)


if __name__ == "__main__":
    main()
