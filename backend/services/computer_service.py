"""
Kautilya AI — Computer Service.

Gives the agent a persistent, per-(user, session) sandboxed workspace: a
directory that survives across tool calls within a chat session, so the
agent can write a file on one turn and read/rerun it on a later turn — the
difference between "a REPL" and "a computer".

Built ON TOP of code_interpreter_service's hardened sandbox (import
whitelist, path guard, resource limits, allowlisted child env) rather than
reimplementing it — this module adds: a session -> workdir registry with
lazy TTL cleanup, byte/file-count quotas, and file read/write/list
operations path-checked against that same workdir.

Explicitly NOT provided: shell/subprocess/os.system execution. The backend
is one shared multi-tenant container with no per-user isolation (no
Docker-in-Docker/E2B/Modal) — raw shell here would be a sandbox-escape/RCE
risk affecting every user on the host. See services/command_service.py's
_DISABLED_FS_COMMANDS for the same reasoning applied to the legacy CLI tools.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.code_interpreter_service import run_python as _sandboxed_run_python

# ── Session registry ────────────────────────────────────────────────────────
_ROOT = Path(tempfile.gettempdir()) / "kautilya_computer"
_TTL_SECONDS = 2 * 60 * 60          # idle sessions are reclaimed after 2h
_SWEEP_EVERY = 20                   # amortize the idle-sweep, don't run it every call

MAX_FILE_BYTES = 5 * 1024 * 1024          # 5MB per file
MAX_SESSION_BYTES = 50 * 1024 * 1024      # 50MB per session workdir
MAX_FILES_PER_SESSION = 200

# Internal dirs written by code_interpreter_service.run_python that shouldn't
# show up as "user files" in [FILE_LIST:] / the Computer panel's file tree.
_HIDDEN_DIRS = {".kt_figs"}

_lock = threading.Lock()
_sessions: Dict[str, Dict[str, Any]] = {}   # key -> {"workdir": Path, "last_used": float}
_call_count = 0


def _key(uid: str, session_id: str) -> str:
    return f"{uid}::{session_id}"


def _sweep_locked():
    now = time.time()
    stale = [k for k, v in _sessions.items() if now - v["last_used"] > _TTL_SECONDS]
    for k in stale:
        wd = _sessions.pop(k)["workdir"]
        try:
            import shutil
            shutil.rmtree(wd, ignore_errors=True)
        except Exception:
            pass


def get_session_dir(uid: str, session_id: str) -> Path:
    """Return the persistent workdir for this (user, session), creating it on first use."""
    global _call_count
    if not uid or not session_id:
        raise ValueError("uid and session_id are required")
    k = _key(uid, session_id)
    with _lock:
        _call_count += 1
        if _call_count % _SWEEP_EVERY == 0:
            _sweep_locked()
        entry = _sessions.get(k)
        if entry is None:
            # uid/session_id come from Firebase auth / our own session-id
            # generator, not raw user text, but scrub defensively anyway —
            # this becomes a real filesystem path.
            safe_uid = "".join(c for c in uid if c.isalnum() or c in "-_")[:80] or "u"
            safe_sid = "".join(c for c in session_id if c.isalnum() or c in "-_")[:80] or "s"
            wd = _ROOT / safe_uid / safe_sid
            wd.mkdir(parents=True, exist_ok=True)
            entry = {"workdir": wd, "last_used": time.time()}
            _sessions[k] = entry
        else:
            entry["last_used"] = time.time()
        return entry["workdir"]


def _safe_join(workdir: Path, name: str) -> Path:
    """Resolve `name` inside `workdir`, rejecting any attempt to escape it."""
    if not name or not isinstance(name, str):
        raise ValueError("a file name is required")
    name = name.strip().lstrip("/\\")
    if not name or name in (".", ".."):
        raise ValueError("invalid file name")
    candidate = (workdir / name).resolve()
    workdir_r = workdir.resolve()
    if candidate != workdir_r and workdir_r not in candidate.parents:
        raise PermissionError(f"'{name}' resolves outside the sandbox workspace")
    if candidate.name in _HIDDEN_DIRS or any(p in _HIDDEN_DIRS for p in candidate.parts):
        raise PermissionError(f"'{name}' is a reserved internal path")
    return candidate


def _session_size_bytes(workdir: Path) -> int:
    total = 0
    for p in workdir.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def write_file(uid: str, session_id: str, name: str, content: str) -> Dict[str, Any]:
    workdir = get_session_dir(uid, session_id)
    path = _safe_join(workdir, name)
    data = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    if len(data) > MAX_FILE_BYTES:
        return {"ok": False, "error": f"file too large ({len(data)} bytes > {MAX_FILE_BYTES} limit)"}
    existing = path.stat().st_size if path.exists() else 0
    if _session_size_bytes(workdir) - existing + len(data) > MAX_SESSION_BYTES:
        return {"ok": False, "error": "session workspace quota exceeded (50MB) — delete unused files first"}
    file_count = sum(1 for p in workdir.rglob("*") if p.is_file())
    if not path.exists() and file_count >= MAX_FILES_PER_SESSION:
        return {"ok": False, "error": f"too many files in this session (limit {MAX_FILES_PER_SESSION})"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"ok": True, "path": str(path.relative_to(workdir)), "bytes": len(data)}


def stage_upload(uid: str, session_id: str, name: str, content_b64: Optional[str] = None,
                  content: Optional[str] = None) -> Dict[str, Any]:
    """Copy a user-uploaded chat attachment into the session workdir so the
    agent can [FILE_READ:]/process it without re-uploading."""
    import base64
    if content_b64:
        workdir = get_session_dir(uid, session_id)
        path = _safe_join(workdir, name)
        data = base64.b64decode(content_b64)
        if len(data) > MAX_FILE_BYTES:
            return {"ok": False, "error": "attachment too large for the sandbox"}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {"ok": True, "path": str(path.relative_to(workdir)), "bytes": len(data)}
    if content is not None:
        return write_file(uid, session_id, name, content)
    return {"ok": False, "error": "no content provided"}


def read_file(uid: str, session_id: str, name: str, max_bytes: int = 200_000) -> Dict[str, Any]:
    workdir = get_session_dir(uid, session_id)
    path = _safe_join(workdir, name)
    if not path.exists() or not path.is_file():
        return {"ok": False, "error": f"'{name}' does not exist in this session's workspace"}
    data = path.read_bytes()
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"ok": False, "error": f"'{name}' is not a text file (binary content)"}
    return {"ok": True, "content": text, "truncated": truncated, "bytes": path.stat().st_size}


def list_files(uid: str, session_id: str) -> List[Dict[str, Any]]:
    workdir = get_session_dir(uid, session_id)
    out = []
    for p in sorted(workdir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(workdir)
        if any(part in _HIDDEN_DIRS for part in rel.parts):
            continue
        try:
            out.append({"path": str(rel).replace(os.sep, "/"), "bytes": p.stat().st_size})
        except OSError:
            pass
    return out


def run_python(uid: str, session_id: str, code: str, timeout: int = 15) -> Dict[str, Any]:
    """Run Python inside this session's persistent workdir (files written by
    a prior [FILE_WRITE:] / run are visible to this run, and vice versa)."""
    workdir = get_session_dir(uid, session_id)
    return _sandboxed_run_python(code, timeout=timeout, workdir=str(workdir))
