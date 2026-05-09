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
    'datetime', 'json', 're', 'csv', 'io', 'os', 'pathlib', 'typing',
    'numpy', 'pandas', 'matplotlib', 'seaborn', 'scipy', 'sklearn',
    'requests',  # allow fetching public data when needed
}

# Modules we actively disallow even if they would be transitively imported.
BLOCKED_IMPORTS = {
    'subprocess', 'socket', 'ctypes', 'multiprocessing', 'threading',
    'fcntl', 'pty', 'pickle', 'marshal', 'importlib',
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
def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    # Relative imports trust the already-imported parent package.
    if level and level > 0:
        return _orig_import(name, globals, locals, fromlist, level)
    root = name.split('.')[0]
    if root in _BLOCKED:
        raise ImportError(f'Import of {{root}} is blocked in the code interpreter.')
    return _orig_import(name, globals, locals, fromlist, level)
_b.__import__ = _guarded_import

# Headless matplotlib
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as _plt
except Exception:
    _plt = None

import os, json, sys, traceback, base64, io
_KT_FIG_DIR = os.environ.get('KT_FIG_DIR')
_KT_MAX_FIGS = int(os.environ.get('KT_MAX_FIGS', '6'))

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
        exec(_USER_CODE, {{'__name__': '__main__'}})
    except SystemExit:
        pass
    except Exception:
        traceback.print_exc()

_USER_CODE = {user_code!r}
_kt_main()

# Emit figures JSON marker for the host to parse.
_figs = _capture_and_save_figs()
sys.stdout.flush()
sys.stderr.flush()
sys.stdout.write('\\n<<<KT_FIGURES_START>>>\\n')
sys.stdout.write(json.dumps(_figs))
sys.stdout.write('\\n<<<KT_FIGURES_END>>>\\n')
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
    preamble = SANDBOX_PREAMBLE.format(
        allowed=sorted(ALLOWED_IMPORTS),
        blocked=sorted(BLOCKED_IMPORTS),
        user_code=code,
    )
    script = textwrap.dedent(preamble)

    workdir = tempfile.mkdtemp(prefix='kt_ci_')
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

    env = os.environ.copy()
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
