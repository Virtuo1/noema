"""Single-command launcher for the Noema backend and frontend."""

from __future__ import annotations

import argparse
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from noema.config import get_settings
from noema.persistence.db import init_db


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="noema",
        description="Start the Noema local-first personal knowledge environment (API + UI).",
    )
    parser.add_argument(
        "--host",
        default=get_settings().host,
        help="Loopback host to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=get_settings().port,
        help="Backend API port (default: 8000)",
    )
    parser.add_argument(
        "--ui-port",
        type=int,
        default=5173,
        help="Frontend Vite dev server port (default: 5173)",
    )
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Run only the FastAPI backend (serves built frontend/dist on the API port if present).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    frontend_dir = repo_root / "frontend"

    # 1. Ensure SQLite schema, WAL mode, foreign keys, FTS5, and local principal are initialized
    init_db()

    processes: list[subprocess.Popen[bytes]] = []

    def _shutdown(_signum: int | None = None, _frame: object | None = None) -> None:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        deadline = time.time() + 3.0
        for proc in processes:
            if proc.poll() is None:
                remaining = max(0.1, deadline - time.time())
                try:
                    proc.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    proc.kill()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # 2. Start FastAPI backend via uvicorn
    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "noema.main:app",
        "--host",
        str(args.host),
        "--port",
        str(args.port),
        "--reload",
    ]
    backend_proc = subprocess.Popen(backend_cmd, cwd=str(repo_root))
    processes.append(backend_proc)

    # 3. Start Vite frontend dev server unless --api-only is passed
    npm_bin = shutil.which("npm")
    if not args.api_only and npm_bin and (frontend_dir / "package.json").exists():
        frontend_cmd = [
            npm_bin,
            "--prefix",
            str(frontend_dir),
            "run",
            "dev",
            "--",
            "--host",
            str(args.host),
            "--port",
            str(args.ui_port),
        ]
        frontend_proc = subprocess.Popen(frontend_cmd, cwd=str(repo_root))
        processes.append(frontend_proc)
        print(
            f"\nNoema is starting:\n"
            f"  → Web UI (dev):  http://{args.host}:{args.ui_port}\n"
            f"  → API & Docs:    http://{args.host}:{args.port}/docs\n"
            f"Press Ctrl+C to stop both services.\n",
            flush=True,
        )
    else:
        print(
            f"\nNoema backend is starting:\n"
            f"  → Application & API: http://{args.host}:{args.port}\n"
            f"  → OpenAPI Docs:      http://{args.host}:{args.port}/docs\n"
            f"Press Ctrl+C to stop.\n",
            flush=True,
        )

    try:
        while True:
            for proc in processes:
                ret = proc.poll()
                if ret is not None:
                    _shutdown()
                    return ret
            time.sleep(0.25)
    except KeyboardInterrupt:
        _shutdown()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
