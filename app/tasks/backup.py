"""Celery task to trigger a backup on demand from admin UI."""

from __future__ import annotations

import subprocess

from app.tasks.celery_app import celery_app


@celery_app.task(name="backup.run")
def run_backup() -> dict:
    result = subprocess.run(
        ["/scripts/backup.sh"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-2000:],
    }
