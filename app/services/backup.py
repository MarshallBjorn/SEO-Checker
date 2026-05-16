"""Wrapper around restic CLI for listing snapshots from the admin UI."""

from __future__ import annotations

import asyncio
import json
import os


async def list_snapshots() -> list[dict]:
    """Return restic snapshots as a list of dicts, or [] on error."""
    if not os.environ.get("RESTIC_REPOSITORY") or not os.environ.get("RESTIC_PASSWORD"):
        return []
    proc = await asyncio.create_subprocess_exec(
        "restic",
        "snapshots",
        "--json",
        env={**os.environ},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _stderr = await proc.communicate()
    if proc.returncode != 0:
        return []
    try:
        return json.loads(stdout or b"[]")
    except json.JSONDecodeError:
        return []
