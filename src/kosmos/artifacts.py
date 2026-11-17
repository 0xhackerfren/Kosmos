"""JSON records and atomic, integrity-checked checkpoints. Never uses pickle."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
from typing import Any

from kosmos import __version__


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def source_digest() -> str:
    """Fingerprint installed Kosmos Python sources; external plugins need their own provenance."""
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def provenance() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    commit, dirty = None, None
    try:
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=5,
        )
        if commit_result.returncode == 0:
            commit = commit_result.stdout.strip()
            status = subprocess.run(
                ["git", "status", "--porcelain"], cwd=root,
                capture_output=True, text=True, timeout=5,
            )
            dirty = bool(status.stdout.strip()) if status.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {
        "package_version": __version__, "source_digest": source_digest(),
        "python": platform.python_version(), "implementation": platform.python_implementation(),
        "system": platform.system(), "git_commit": commit, "git_dirty": dirty,
    }


def write_json(path: Path, value: Any) -> None:
    """Replace on the same filesystem, avoiding partially written checkpoint files."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".kosmos-", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(canonical(value) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def write_checkpoint(path: Path, state: dict[str, Any]) -> str:
    payload = {
        "checkpoint_version": 1, "source_digest": source_digest(),
        "python": platform.python_version(), "state": state,
    }
    digest = hashlib.sha256(canonical(payload).encode()).hexdigest()
    write_json(path, {"sha256": digest, "payload": payload})
    return digest


def read_checkpoint(path: Path) -> tuple[dict[str, Any], str]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    payload = document["payload"]
    digest = hashlib.sha256(canonical(payload).encode()).hexdigest()
    if digest != document["sha256"]:
        raise ValueError("Checkpoint checksum mismatch")
    if payload["checkpoint_version"] != 1:
        raise ValueError("Unsupported checkpoint envelope")
    if payload["source_digest"] != source_digest():
        raise ValueError("Checkpoint was produced by different Kosmos source; migration is required")
    if payload["python"] != platform.python_version():
        raise ValueError("Resume requires the same Python version")
    return payload["state"], digest
