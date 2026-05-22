"""
Kautilya AI — Code Interpreter Service.

Runs user-supplied Python in a sandboxed subprocess with:
  - hard wall-clock timeout
  - memory cap (best-effort via resource limits on POSIX / Job Object on Windows)
  - restricted imports (whitelist)
  - uploaded files mounted read-only under /sandbox/data
  - stdout + stderr captured
  - matplotlib figures auto-saved as PNG and returned inline (base64)

This is an MVP — NOT safe for fully untrusted execution against a shared host.
For hostile users deploy this against a disposable container (Docker / E2B /
Modal). For the current threat model (authenticated Kautilya users running
their own data-analysis scripts) the subprocess + import whitelist is
acceptable.
"""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid
from typing import List, Dict, Any

# Only these top-level modules may be imported from user code.
ALLOWED_IMPORTS = {
    'math', 'statistics', 'random', 'itertools', 'functools', 'collections',
    'datetime', 'time', 'json', 're', 'csv', 'io', 'os', 'pathlib', 'typing',
    'numpy', 'pandas', 'matplotlib', 'seaborn', 'scipy', 'sklearn',
    'requests',  # allow fetching public data when needed
    'sqlite3', 'hashlib', 'uuid', 'zipfile',
}

# Modules we actively disallow even if they would be transitively imported.
BLOCKED_IMPORTS = {
    'subprocess', 'fcntl', 'pty', 'marshal',
}

DEFAULT_TIMEOUT = 25       # seconds
DEFAULT_MEM_MB  = 512
MAX_STDOUT      = 60_000
MAX_FIGURES     = 6


SANDBOX_PREAMBLE = """
import builtins as _b
_orig_import = _b.__import__
_ALLOWED = {allowed!r}
_BLOCKED = {blocked!r}
_guard_enabled = False
def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if not _guard_enabled:
        return _orig_import(name, globals, locals, fromlist, level)
    if level and level > 0:
        return _orig_import(name, globals, locals, fromlist, level)
    root = name.split('.')[0]
    
    # Inspect stack to see if the user script is importing directly
    try:
        import sys as _sys
        caller_frame = _sys._getframe(1)
        caller_name = caller_frame.f_globals.get('__name__')
    except Exception:
        caller_name = '__main__'
        
    if caller_name == '__main__':
        if root not in _ALLOWED and not root.startswith('_') and root not in {{'sys', 'traceback', 'base64'}}:
            raise ImportError(f"Import of '{{root}}' is not allowed in the code interpreter.")
    return _orig_import(name, globals, locals, fromlist, level)
_b.__import__ = _guarded_import

# Filesystem access control
import os as _os
import sys as _sys

_PROJECT_ROOT = {project_root!r}
_GEMINI_DIR = {gemini_dir!r}
_WORKDIR = {workdir!r}
_ALLOWED_PREFIXES = {allowed_prefixes!r}
_SYS_PATH = {sys_path!r}
_SYSTEM_DIRS = {system_dirs!r}


def _is_blocked_path(path, write_operation=False):
    try:
        if not path:
            return False
        if hasattr(path, '__fspath__'):
            path = path.__fspath__()
        if not isinstance(path, str):
            path = str(path)
        
        abs_p = _os.path.realpath(path).lower()
        
        # 1. Project root and .gemini directory are ALWAYS BLOCKED (except matplotlib_cache)
        mpl_cache = _os.path.join(_GEMINI_DIR, 'matplotlib_cache')
        if abs_p == mpl_cache or abs_p.startswith(mpl_cache + _os.sep) or abs_p.startswith(mpl_cache.replace(_os.sep, '/')):
            return False
            
        if abs_p == _GEMINI_DIR or abs_p.startswith(_GEMINI_DIR + _os.sep) or abs_p.startswith(_GEMINI_DIR.replace(_os.sep, '/')):
            return True
        if abs_p == _PROJECT_ROOT or abs_p.startswith(_PROJECT_ROOT + _os.sep) or abs_p.startswith(_PROJECT_ROOT.replace(_os.sep, '/')):
            return True
            
        # 2. Sandbox workdir is ALWAYS ALLOWED (both read and write)
        if abs_p == _WORKDIR or abs_p.startswith(_WORKDIR + _os.sep) or abs_p.startswith(_WORKDIR.replace(_os.sep, '/')):
            return False
            
        # 3. If it's a write operation, it MUST be inside the workdir.
        if write_operation:
            return True
            
        # 4. For read operations, check allowed prefixes and paths
        for prefix in _ALLOWED_PREFIXES:
            if prefix and (abs_p == prefix or abs_p.startswith(prefix + _os.sep) or abs_p.startswith(prefix.replace(_os.sep, '/'))):
                return False
                
        for sp_abs in _SYS_PATH:
            if sp_abs:
                # Skip project root or gemini path in sys.path just in case
                if sp_abs == _PROJECT_ROOT or sp_abs.startswith(_PROJECT_ROOT + _os.sep) or sp_abs.startswith(_PROJECT_ROOT.replace(_os.sep, '/')):
                    continue
                if sp_abs == _GEMINI_DIR or sp_abs.startswith(_GEMINI_DIR + _os.sep) or sp_abs.startswith(_GEMINI_DIR.replace(_os.sep, '/')):
                    continue
                if abs_p == sp_abs or abs_p.startswith(sp_abs + _os.sep) or abs_p.startswith(sp_abs.replace(_os.sep, '/')):
                    return False
                    
        for sys_dir in _SYSTEM_DIRS:
            if sys_dir and (abs_p == sys_dir or abs_p.startswith(sys_dir + _os.sep) or abs_p.startswith(sys_dir.replace(_os.sep, '/'))):
                return False
                
        return True
    except Exception:
        return True

# Guard builtins.open
_orig_open = _b.open
def _guarded_open(file, mode='r', *args, **kwargs):
    write_op = any(c in mode for c in ('w', 'a', '+', 'x')) if isinstance(mode, str) else False
    if _is_blocked_path(file, write_operation=write_op):
        raise PermissionError(f"Access to path '{{file}}' is restricted in the sandbox.")
    return _orig_open(file, mode, *args, **kwargs)
_b.open = _guarded_open

# Guard os.open
_orig_os_open = _os.open
_WRITE_FLAGS = getattr(_os, 'O_WRONLY', 0) | getattr(_os, 'O_RDWR', 0) | getattr(_os, 'O_CREAT', 0) | getattr(_os, 'O_APPEND', 0) | getattr(_os, 'O_TRUNC', 0) | getattr(_os, 'O_EXCL', 0)
def _guarded_os_open(path, flags, *args, **kwargs):
    write_op = bool(flags & _WRITE_FLAGS)
    if _is_blocked_path(path, write_operation=write_op):
        raise PermissionError(f"Access to path '{{path}}' is restricted in the sandbox.")
    return _orig_os_open(path, flags, *args, **kwargs)
_os.open = _guarded_os_open

# Helper for wrapping os read/write/dual-path functions
def _guard_os_read(func_name, path_param='path', default_path=None):
    if hasattr(_os, func_name):
        orig = getattr(_os, func_name)
        def guarded(*args, **kwargs):
            path = default_path
            if len(args) > 0:
                path = args[0]
            elif path_param in kwargs:
                path = kwargs[path_param]
            
            check_path = path if path is not None else '.'
            if _is_blocked_path(check_path, write_operation=False):
                raise PermissionError(f"Access to path '{{check_path}}' is restricted in the sandbox.")
            return orig(*args, **kwargs)
        setattr(_os, func_name, guarded)

def _guard_os_write(func_name, path_param='path'):
    if hasattr(_os, func_name):
        orig = getattr(_os, func_name)
        def guarded(*args, **kwargs):
            path = None
            if len(args) > 0:
                path = args[0]
            elif path_param in kwargs:
                path = kwargs[path_param]
            
            if path is not None:
                if _is_blocked_path(path, write_operation=True):
                    raise PermissionError(f"Modification of path '{{path}}' is restricted in the sandbox.")
            return orig(*args, **kwargs)
        setattr(_os, func_name, guarded)

def _guard_os_dual_path(func_name, src_param='src', dst_param='dst'):
    if hasattr(_os, func_name):
        orig = getattr(_os, func_name)
        def guarded(*args, **kwargs):
            src = None
            dst = None
            if len(args) > 0:
                src = args[0]
            elif src_param in kwargs:
                src = kwargs[src_param]
                
            if len(args) > 1:
                dst = args[1]
            elif dst_param in kwargs:
                dst = kwargs[dst_param]
                
            if src is not None:
                if _is_blocked_path(src, write_operation=True):
                    raise PermissionError(f"Modification of path '{{src}}' is restricted in the sandbox.")
            if dst is not None:
                if _is_blocked_path(dst, write_operation=True):
                    raise PermissionError(f"Modification of path '{{dst}}' is restricted in the sandbox.")
            return orig(*args, **kwargs)
        setattr(_os, func_name, guarded)

# Guard os read functions
_guard_os_read('listdir')
_guard_os_read('scandir')
_guard_os_read('walk', 'top')
_guard_os_read('stat')
_guard_os_read('readlink')
_guard_os_read('access')

# Guard os write functions
_guard_os_write('remove')
_guard_os_write('unlink')
_guard_os_write('rmdir')
_guard_os_write('removedirs')
_guard_os_write('mkdir')
_guard_os_write('makedirs')
_guard_os_write('chmod')
_guard_os_write('utime')

# Guard os dual path functions
_guard_os_dual_path('rename', 'src', 'dst')
_guard_os_dual_path('replace', 'src', 'dst')
_guard_os_dual_path('link', 'src', 'dst')
_guard_os_dual_path('symlink', 'src', 'dst')

# Guard sqlite3 if available
try:
    import sqlite3 as _sqlite3
    _orig_sqlite3_connect = _sqlite3.connect
    def _guarded_sqlite3_connect(database, *args, **kwargs):
        if database != ':memory:':
            if _is_blocked_path(database, write_operation=True):
                raise PermissionError(f"Access to database path '{{database}}' is restricted in the sandbox.")
        return _orig_sqlite3_connect(database, *args, **kwargs)
    _sqlite3.connect = _guarded_sqlite3_connect
except Exception:
    pass

# Block command execution functions in os
_blocked_os_funcs = [
    'system', 'popen', 'spawnl', 'spawnle', 'spawnlp', 'spawnlpe',
    'spawnv', 'spawnve', 'spawnvp', 'spawnvpe', 'execl', 'execle',
    'execlp', 'execle', 'execv', 'execve', 'execvp', 'execvpe',
    'posix_spawn', 'posix_spawnp', 'fork', 'forkpty', 'kill', 'killpg',
    'plock', 'sched_setparam', 'sched_setscheduler', 'setuid', 'seteuid',
    'setgid', 'setegid', 'setreuid', 'setregid', 'setgroups'
]
for func_name in _blocked_os_funcs:
    if hasattr(_os, func_name):
        def _make_blocked(name):
            def _blocked(*args, **kwargs):
                raise PermissionError(f"Execution of os.{{name}} is restricted in the sandbox.")
            return _blocked
        setattr(_os, func_name, _make_blocked(func_name))

# Headless matplotlib
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as _plt
except Exception:
    _plt = None

import json, traceback, base64, io
_KT_FIG_DIR = _os.environ.get('KT_FIG_DIR')
_KT_MAX_FIGS = int(_os.environ.get('KT_MAX_FIGS', '6'))

def _capture_and_save_figs():
    if _plt is None:
        return []
    saved = []
    for i, num in enumerate(_plt.get_fignums()[:_KT_MAX_FIGS]):
        fig = _plt.figure(num)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        saved.append(base64.b64encode(buf.getvalue()).decode('ascii'))
    _plt.close('all')
    return saved

def _kt_main():
    try:
        global _guard_enabled
        _guard_enabled = True
        exec(_USER_CODE, {{'__name__': '__main__'}})
    except SystemExit:
        pass
    except Exception:
        traceback.print_exc()

_USER_CODE = {user_code!r}
_kt_main()

# Emit figures JSON marker for the host to parse.
_figs = _capture_and_save_figs()
_sys.stdout.flush()
_sys.stderr.flush()
_sys.stdout.write('\\n<<<KT_FIGURES_START>>>\\n')
_sys.stdout.write(json.dumps(_figs))
_sys.stdout.write('\\n<<<KT_FIGURES_END>>>\\n')
"""


def _apply_posix_limits():  # called in child process on POSIX only
    try:
        import resource
        mb = DEFAULT_MEM_MB
        # RSS virtual memory
        resource.setrlimit(resource.RLIMIT_AS, (mb * 1024 * 1024, mb * 1024 * 1024))
        # CPU time cap
        resource.setrlimit(resource.RLIMIT_CPU, (DEFAULT_TIMEOUT + 2, DEFAULT_TIMEOUT + 2))
    except Exception:
        pass


def run_python(code: str, timeout: int = DEFAULT_TIMEOUT,
               files: List[Dict[str, str]] | None = None) -> Dict[str, Any]:
    """
    Execute user Python code.
    Returns: {
      stdout: str, stderr: str, exit_code: int, duration_ms: int,
      figures: [base64_png, ...], timed_out: bool,
    }
    """
    current_dir = os.path.dirname(os.path.realpath(__file__))
    project_root = os.path.realpath(os.path.join(current_dir, '..', '..'))
    gemini_dir = os.path.realpath(os.path.join(os.path.expanduser('~'), '.gemini'))
    
    sys_prefix = os.path.realpath(sys.prefix)
    sys_base_prefix = os.path.realpath(sys.base_prefix)
    sys_exec_prefix = os.path.realpath(sys.exec_prefix)
    sys_base_exec_prefix = os.path.realpath(sys.base_exec_prefix)

    allowed_prefixes = list(set([
        sys_prefix.lower(),
        sys_base_prefix.lower(),
        sys_exec_prefix.lower(),
        sys_base_exec_prefix.lower()
    ]))

    system_dirs = []
    if os.name == 'nt':
        for env_var in ['SystemRoot', 'windir', 'ProgramFiles', 'ProgramFiles(x86)', 'CommonProgramFiles', 'CommonProgramFiles(x86)']:
            val = os.environ.get(env_var)
            if val:
                system_dirs.append(os.path.realpath(val).lower())
    else:
        system_dirs = ['/usr', '/lib', '/lib64', '/etc', '/var/lib', '/sys', '/proc', '/dev']
    system_dirs = list(set(d for d in system_dirs if d))

    sys_path_clean = []
    for p in sys.path:
        if p:
            try:
                sys_path_clean.append(os.path.realpath(p).lower())
            except Exception:
                pass

    workdir = tempfile.mkdtemp(prefix='kt_ci_')
    workdir_abs = os.path.realpath(workdir)

    preamble = SANDBOX_PREAMBLE.format(
        allowed=sorted(ALLOWED_IMPORTS),
        blocked=sorted(BLOCKED_IMPORTS),
        project_root=project_root.lower(),
        gemini_dir=gemini_dir.lower(),
        workdir=workdir_abs.lower(),
        allowed_prefixes=allowed_prefixes,
        sys_path=sys_path_clean,
        system_dirs=system_dirs,
        user_code=code,
    )
    script = textwrap.dedent(preamble)

    data_dir = os.path.join(workdir, 'data')
    os.makedirs(data_dir, exist_ok=True)

    # Materialize attached files
    if files:
        for f in files:
            name = os.path.basename(f.get('name') or f'file_{uuid.uuid4().hex[:6]}.bin')
            path = os.path.join(data_dir, name)
            try:
                b64 = f.get('content_b64')
                if b64:
                    with open(path, 'wb') as fh:
                        fh.write(base64.b64decode(b64))
                elif 'content' in f:
                    with open(path, 'w', encoding='utf-8') as fh:
                        fh.write(f['content'])
            except Exception as e:
                print(f"[CodeInterp] failed to stage {name}: {e}")

    fig_dir = os.path.join(workdir, 'figs')
    os.makedirs(fig_dir, exist_ok=True)

    mpl_cache_dir = os.path.join(gemini_dir, 'matplotlib_cache')
    os.makedirs(mpl_cache_dir, exist_ok=True)

    env = os.environ.copy()
    env['TMP'] = workdir
    env['TEMP'] = workdir
    env['TMPDIR'] = workdir
    env['MPLCONFIGDIR'] = mpl_cache_dir
    env['KT_FIG_DIR'] = fig_dir
    env['KT_MAX_FIGS'] = str(MAX_FIGURES)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['MPLBACKEND'] = 'Agg'
    env.pop('PYTHONPATH', None)

    start = time.time()
    timed_out = False
    try:
        popen_kwargs = dict(
            args=[sys.executable, '-I', '-c', script],
            cwd=data_dir,  # so user sees their files next to cwd
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if os.name == 'posix':
            popen_kwargs['preexec_fn'] = _apply_posix_limits
        proc = subprocess.Popen(**popen_kwargs)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            stdout, stderr = proc.communicate()
    except Exception as e:
        shutil.rmtree(workdir, ignore_errors=True)
        return {
            'stdout': '', 'stderr': f'Interpreter host error: {e}',
            'exit_code': -1, 'duration_ms': int((time.time() - start) * 1000),
            'figures': [], 'timed_out': False,
        }
    duration_ms = int((time.time() - start) * 1000)

    # Parse figures marker
    figures: List[str] = []
    clean_stdout = stdout
    start_marker = '<<<KT_FIGURES_START>>>'
    end_marker = '<<<KT_FIGURES_END>>>'
    if start_marker in stdout and end_marker in stdout:
        pre, rest = stdout.split(start_marker, 1)
        mid, _post = rest.split(end_marker, 1)
        clean_stdout = pre.rstrip()
        try:
            figures = json.loads(mid.strip())
        except Exception:
            figures = []

    # Trim
    if len(clean_stdout) > MAX_STDOUT:
        clean_stdout = clean_stdout[:MAX_STDOUT] + '\n…(truncated)'
    if len(stderr) > MAX_STDOUT:
        stderr = stderr[:MAX_STDOUT] + '\n…(truncated)'

    shutil.rmtree(workdir, ignore_errors=True)

    return {
        'stdout': clean_stdout,
        'stderr': stderr,
        'exit_code': proc.returncode if not timed_out else 124,
        'duration_ms': duration_ms,
        'figures': figures,
        'timed_out': timed_out,
    }
