"""
Kautilya AI — MCP (Model Context Protocol) Client Service

Spawns and manages stdio-based MCP servers declared in `backend/mcp_config.json`,
discovers their exposed tools, and provides a SYNC facade that the existing
agent_loop (which is sync/threaded) can call without knowing the MCP SDK is async.

Architecture:
  - A single asyncio event loop runs in a daemon thread for the life of the app.
  - On `init_mcp()` each enabled server is spawned via stdio; ClientSession is
    kept open. Tools are listed and cached as OpenAI-format function specs.
  - Tools are namespaced as `mcp_<server_key>_<tool>` so they share the same
    `[INTEGRATION: tool_name | {...}]` dispatch pipeline as integration_tools.py.
  - Sync callers use `available_mcp_tools()` and `execute_mcp_tool(name, args)`;
    both schedule coroutines on the background loop via run_coroutine_threadsafe.

Failure modes are silent and degraded — if a server fails to spawn (npx missing,
bad creds, unreachable), it is marked `error` and the rest of the app continues.
The MCP_DISABLED env var skips initialisation entirely.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------- Module state ----------
_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_thread: Optional[threading.Thread] = None
_sessions: Dict[str, Any] = {}        # server_key -> ClientSession
_exit_stacks: Dict[str, Any] = {}     # server_key -> AsyncExitStack (keeps stdio open)
_tools_by_server: Dict[str, List[Dict[str, Any]]] = {}  # server_key -> [tool_spec]
_server_status: Dict[str, Dict[str, Any]] = {}  # server_key -> {state, error, category, description, tool_count}
_initialized_users = set()            # Set of user IDs that have run init_user_mcp
_initialized = False
_lock = threading.Lock()


def _config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "mcp_config.json"


def _load_config() -> Dict[str, Any]:
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"servers": {}}
    except Exception as e:
        print(f"[MCP] config load error: {e}")
        return {"servers": {}}


def _expand_env(value: Any) -> Any:
    """Substitute ${VAR} occurrences from os.environ. Returns None if any
    required var is missing (caller treats that as 'skip')."""
    if isinstance(value, str):
        def _sub(m):
            return os.environ.get(m.group(1), "")
        return re.sub(r"\$\{([A-Z0-9_]+)\}", _sub, value)
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def _sanitize_name(s: str) -> str:
    """Tool names must match ^[a-z0-9_]+$ for the [INTEGRATION:] regex."""
    return re.sub(r"[^a-z0-9_]", "_", s.lower())


def _start_loop():
    """Spin up the persistent asyncio loop on a daemon thread."""
    global _loop, _loop_thread
    if _loop and _loop.is_running():
        return
    ready = threading.Event()

    def runner():
        global _loop
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        ready.set()
        _loop.run_forever()

    _loop_thread = threading.Thread(target=runner, daemon=True, name="mcp-loop")
    _loop_thread.start()
    ready.wait(timeout=5)


def _run_coro(coro, timeout: float = 30.0):
    """Schedule a coroutine on the background loop and block until done."""
    if not _loop:
        raise RuntimeError("MCP event loop not started")
    fut = asyncio.run_coroutine_threadsafe(coro, _loop)
    return fut.result(timeout=timeout)


# ---------- Server lifecycle ----------
async def _spawn_server(server_key: str, cfg: Dict[str, Any]) -> None:
    """Connect to one MCP server via stdio. Mutates _sessions / _tools_by_server.
    Stores failure reason in _server_status without raising."""
    # Lazy imports — the mcp package may not be installed in dev envs.
    from contextlib import AsyncExitStack
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    # Validate required env vars first; missing creds = skip with clear reason.
    missing = [v for v in cfg.get("env_required", []) if not os.environ.get(v)]
    if missing:
        _server_status[server_key] = {
            "state": "missing_env",
            "error": f"Missing env: {', '.join(missing)}",
            "category": cfg.get("category", "Other"),
            "description": cfg.get("description", ""),
            "tool_count": 0,
        }
        return

    command = _expand_env(cfg["command"])
    args = _expand_env(cfg.get("args", []))

    params = StdioServerParameters(
        command=command,
        args=args,
        env={**os.environ, **cfg.get("env", {})},
    )

    stack = AsyncExitStack()
    try:
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        # Discover tools
        tools_resp = await session.list_tools()
        specs = []
        for t in tools_resp.tools:
            tool_name = f"mcp_{_sanitize_name(server_key)}_{_sanitize_name(t.name)}"
            schema = t.inputSchema or {"type": "object", "properties": {}}
            specs.append({
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": (t.description or t.name)[:512],
                    "parameters": schema,
                    "_mcp_server": server_key,
                    "_mcp_tool": t.name,
                },
            })

        _sessions[server_key] = session
        _exit_stacks[server_key] = stack
        _tools_by_server[server_key] = specs
        _server_status[server_key] = {
            "state": "active",
            "error": None,
            "category": cfg.get("category", "Other"),
            "description": cfg.get("description", ""),
            "tool_count": len(specs),
        }
        print(f"[MCP] OK: '{server_key}' connected with {len(specs)} tools")
    except Exception as e:
        # Clean up partial stack on failure
        try:
            await stack.aclose()
        except Exception:
            pass
        _server_status[server_key] = {
            "state": "error",
            "error": str(e)[:200],
            "category": cfg.get("category", "Other"),
            "description": cfg.get("description", ""),
            "tool_count": 0,
        }
        print(f"[MCP] ERR: '{server_key}' failed: {e}")


async def _init_all(config: Dict[str, Any]):
    """Spawn every enabled server concurrently — one failure does not block
    the others. Servers that are disabled in config are marked 'disabled'."""
    servers = config.get("servers", {})
    tasks = []
    for key, cfg in servers.items():
        if not cfg.get("enabled"):
            _server_status[key] = {
                "state": "disabled",
                "error": None,
                "category": cfg.get("category", "Other"),
                "description": cfg.get("description", ""),
                "tool_count": 0,
            }
            continue
        tasks.append(_spawn_server(key, cfg))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def init_mcp():
    """Idempotent startup hook — call from app.py after Flask init."""
    global _initialized
    with _lock:
        if _initialized:
            return
        if os.environ.get("MCP_DISABLED", "").lower() in ("1", "true", "yes"):
            print("[MCP] disabled via MCP_DISABLED env")
            _initialized = True
            return
        try:
            _start_loop()
            config = _load_config()
            _run_coro(_init_all(config), timeout=60)
            active = sum(1 for s in _server_status.values() if s["state"] == "active")
            total_tools = sum(s["tool_count"] for s in _server_status.values())
            print(f"[MCP] initialised: {active}/{len(_server_status)} servers active, {total_tools} tools available")
        except ImportError:
            print("[MCP] mcp SDK not installed — skipping (pip install mcp to enable)")
        except Exception as e:
            print(f"[MCP] init failed: {e}")
        _initialized = True


# ---------- Sync facade for agent_loop ----------
# ---------- User Custom MCP Server lifecycle ----------
async def _spawn_user_mcp(uid: str, server_key: str, cfg: Dict[str, Any]) -> None:
    from contextlib import AsyncExitStack
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    
    db_key = f"user:{uid}:{server_key}"
    url = cfg.get("url")
    if not url:
        _server_status[db_key] = {
            "state": "error",
            "error": "Missing url in config",
            "category": cfg.get("category", "Custom"),
            "description": cfg.get("description", ""),
            "tool_count": 0,
            "url": "",
        }
        return
        
    stack = AsyncExitStack()
    try:
        # Connect via SSE client
        read, write = await stack.enter_async_context(sse_client(url))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        
        # Discover tools
        tools_resp = await session.list_tools()
        specs = []
        for t in tools_resp.tools:
            tool_name = f"mcp_{_sanitize_name(server_key)}_{_sanitize_name(t.name)}"
            schema = t.inputSchema or {"type": "object", "properties": {}}
            specs.append({
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": (t.description or t.name)[:512],
                    "parameters": schema,
                    "_mcp_server": server_key,
                    "_mcp_tool": t.name,
                    "_mcp_user_id": uid,
                },
            })
            
        _sessions[db_key] = session
        _exit_stacks[db_key] = stack
        _tools_by_server[db_key] = specs
        _server_status[db_key] = {
            "state": "active",
            "error": None,
            "category": cfg.get("category", "Custom"),
            "description": cfg.get("description", ""),
            "tool_count": len(specs),
            "url": url,
        }
        print(f"[MCP] OK: User {uid} '{server_key}' connected with {len(specs)} tools via SSE")
    except Exception as e:
        try:
            await stack.aclose()
        except Exception:
            pass
        _server_status[db_key] = {
            "state": "error",
            "error": str(e)[:200],
            "category": cfg.get("category", "Custom"),
            "description": cfg.get("description", ""),
            "tool_count": 0,
            "url": url,
        }
        print(f"[MCP] ERR: User {uid} '{server_key}' failed: {e}")


def init_user_mcp(uid: str):
    """Fetch enabled custom MCP servers for this user from Firestore and connect to them."""
    if not uid:
        return
    with _lock:
        if uid in _initialized_users:
            return
        _initialized_users.add(uid)

    from extensions import db
    if not db:
        return

    try:
        docs = db.collection('users').document(uid).collection('mcp_servers').stream()
        for doc in docs:
            cfg = doc.to_dict()
            key = doc.id
            if cfg.get("enabled", True):
                init_user_mcp_server(uid, key, cfg)
    except Exception as e:
        print(f"[MCP] Failed to init custom servers for user {uid}: {e}")


def init_user_mcp_server(uid: str, key: str, cfg: Dict[str, Any]):
    """Connect to a single user custom MCP server (or reconnect if configuration changed)."""
    close_user_mcp_server(uid, key)
    
    if _loop and _loop.is_running():
        try:
            _run_coro(_spawn_user_mcp(uid, key, cfg), timeout=15.0)
        except Exception as e:
            print(f"[MCP] Failed to connect user custom server {key}: {e}")


def close_user_mcp_server(uid: str, key: str):
    """Gracefully close and clean up connection resources for a user server."""
    db_key = f"user:{uid}:{key}"
    
    async def _close():
        stack = _exit_stacks.get(db_key)
        if stack:
            try:
                await stack.aclose()
            except Exception:
                pass
            _exit_stacks.pop(db_key, None)
        _sessions.pop(db_key, None)
        _tools_by_server.pop(db_key, None)
        _server_status.pop(db_key, None)
        
    if _loop and _loop.is_running():
        try:
            _run_coro(_close(), timeout=10.0)
        except Exception:
            pass


# ---------- Sync facade for agent_loop ----------
def available_mcp_tools(uid: Optional[str] = None) -> List[Dict[str, Any]]:
    """All tool specs from connected MCP servers, OpenAI function format.
    Safe to call even before init_mcp — returns []."""
    out = []
    
    # 1. Global tools
    for key, specs in _tools_by_server.items():
        if not key.startswith("user:"):
            out.extend(specs)
            
    # 2. User specific tools
    if uid:
        try:
            init_user_mcp(uid)
        except Exception as e:
            print(f"[MCP] Failed to init user {uid} custom MCP tools: {e}")
        
        user_prefix = f"user:{uid}:"
        for key, specs in _tools_by_server.items():
            if key.startswith(user_prefix):
                out.extend(specs)
                
    return out


def execute_mcp_tool(name: str, args: Dict[str, Any], timeout: float = 30.0, uid: Optional[str] = None) -> Dict[str, Any]:
    """Sync dispatcher. `name` is the full `mcp_<server>_<tool>` namespaced name.
    Returns {ok, result | error}."""
    if not name.startswith("mcp_"):
        return {"ok": False, "error": "not an MCP tool name"}

    # Find which server owns it
    target_server = None
    target_tool = None
    
    # First search user-specific servers if uid is passed
    if uid:
        user_prefix = f"user:{uid}:"
        for server_key, specs in _tools_by_server.items():
            if server_key.startswith(user_prefix):
                for spec in specs:
                    if spec["function"]["name"] == name:
                        target_server = server_key
                        target_tool = spec["function"]["_mcp_tool"]
                        break
            if target_server:
                break
                
    # If not found in user servers, search global servers
    if not target_server:
        for server_key, specs in _tools_by_server.items():
            if not server_key.startswith("user:"):
                for spec in specs:
                    if spec["function"]["name"] == name:
                        target_server = server_key
                        target_tool = spec["function"]["_mcp_tool"]
                        break
            if target_server:
                break

    if not target_server:
        return {"ok": False, "error": f"unknown MCP tool: {name}"}

    session = _sessions.get(target_server)
    if not session:
        return {"ok": False, "error": f"MCP server '{target_server}' not connected"}

    async def _call():
        return await session.call_tool(target_tool, args or {})

    try:
        result = _run_coro(_call(), timeout=timeout)
        content = []
        for c in (result.content or []):
            if hasattr(c, "text"):
                content.append({"type": "text", "text": c.text})
            elif hasattr(c, "data"):
                content.append({"type": "data", "data": str(c.data)[:1000]})
            else:
                content.append({"type": "raw", "value": str(c)[:500]})
        return {
            "ok": not getattr(result, "isError", False),
            "result": content,
            "server": target_server.split(":")[-1] if ":" in target_server else target_server,
        }
    except asyncio.TimeoutError:
        return {"ok": False, "error": f"MCP tool '{name}' timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def is_mcp_tool(name: str) -> bool:
    return name.startswith("mcp_") and any(
        spec["function"]["name"] == name
        for specs in _tools_by_server.values()
        for spec in specs
    )


def get_mcp_status(uid: Optional[str] = None) -> Dict[str, Any]:
    """Snapshot used by /api/mcp/status and the UI dialog."""
    config = _load_config()
    servers_cfg = config.get("servers", {})
    out_servers = []
    
    # 1. Global servers
    for key, cfg in servers_cfg.items():
        status = _server_status.get(key, {
            "state": "disabled",
            "error": None,
            "category": cfg.get("category", "Other"),
            "description": cfg.get("description", ""),
            "tool_count": 0,
        })
        tools = _tools_by_server.get(key, [])
        out_servers.append({
            "key": key,
            "name": f"mcp-{key.replace('_', '-')}-server",
            "category": status.get("category") or cfg.get("category", "Other"),
            "description": status.get("description") or cfg.get("description", ""),
            "state": status["state"],
            "error": status.get("error"),
            "tool_count": status["tool_count"],
            "enabled_in_config": bool(cfg.get("enabled")),
            "env_required": cfg.get("env_required", []),
            "tools": [
                {"name": t["function"]["name"], "underlying": t["function"]["_mcp_tool"]}
                for t in tools
            ],
        })
        
    # 2. User custom servers
    if uid:
        try:
            init_user_mcp(uid)
        except Exception as e:
            print(f"[MCP] Failed to init custom servers on status: {e}")
            
        user_prefix = f"user:{uid}:"
        for db_key, status in _server_status.items():
            if db_key.startswith(user_prefix):
                server_key = db_key[len(user_prefix):]
                tools = _tools_by_server.get(db_key, [])
                out_servers.append({
                    "key": server_key,
                    "name": f"mcp-{server_key.replace('_', '-')}-server",
                    "category": status.get("category", "Custom"),
                    "description": status.get("description", ""),
                    "state": status["state"],
                    "error": status.get("error"),
                    "tool_count": status["tool_count"],
                    "enabled_in_config": True,
                    "is_custom": True,
                    "url": status.get("url", ""),
                    "tools": [
                        {"name": t["function"]["name"], "underlying": t["function"]["_mcp_tool"]}
                        for t in tools
                    ],
                })
                
    total_active = sum(1 for s in out_servers if s["state"] == "active")
    return {
        "initialized": _initialized,
        "active_count": total_active,
        "total_count": len(out_servers),
        "total_tools": sum(s["tool_count"] for s in out_servers),
        "servers": out_servers,
    }


def shutdown_mcp():
    """Best-effort cleanup. Flask/gunicorn workers rarely call this but it
    keeps `pytest` clean and is safe to invoke multiple times."""
    if not _loop or not _loop.is_running():
        return

    async def _close():
        for key, stack in list(_exit_stacks.items()):
            try:
                await stack.aclose()
            except Exception as e:
                print(f"[MCP] shutdown error for {key}: {e}")
        _exit_stacks.clear()
        _sessions.clear()
        _tools_by_server.clear()
        _server_status.clear()
        with _lock:
            _initialized_users.clear()

    try:
        _run_coro(_close(), timeout=10)
    except Exception:
        pass
    try:
        _loop.call_soon_threadsafe(_loop.stop)
    except Exception:
        pass

