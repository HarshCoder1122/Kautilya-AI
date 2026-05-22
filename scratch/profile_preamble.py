import sys
import os
import time

script_code = """
import time
t_start = time.time()

import os as _os
import sys as _sys
import builtins as _b

_PROJECT_ROOT = r"c:\\Users\\Harsh Vardhan\\OneDrive - ScatterPie Analytics Private Limited\\Desktop\\personal\\jarvis".lower()
_GEMINI_DIR = r"C:\\Users\\Harsh Vardhan\\.gemini".lower()
_WORKDIR = r"C:\\Users\\Harsh Vardhan\\AppData\\Local\\Temp\\dummy_workdir".lower()
_ALLOWED_PREFIXES = []
_SYS_PATH = [_os.path.realpath(p).lower() for p in _sys.path if p]
_SYSTEM_DIRS = []

call_count = 0
total_guard_time = 0.0

def _is_blocked_path(path, write_operation=False):
    global call_count, total_guard_time
    t0 = time.time()
    call_count += 1
    try:
        if not path:
            return False
        if hasattr(path, '__fspath__'):
            path = path.__fspath__()
        if not isinstance(path, str):
            path = str(path)
        
        abs_p = _os.path.realpath(path).lower()
        
        if abs_p == _GEMINI_DIR or abs_p.startswith(_GEMINI_DIR + _os.sep) or abs_p.startswith(_GEMINI_DIR.replace(_os.sep, '/')):
            return True
        if abs_p == _PROJECT_ROOT or abs_p.startswith(_PROJECT_ROOT + _os.sep) or abs_p.startswith(_PROJECT_ROOT.replace(_os.sep, '/')):
            return True
            
        if abs_p == _WORKDIR or abs_p.startswith(_WORKDIR + _os.sep) or abs_p.startswith(_WORKDIR.replace(_os.sep, '/')):
            return False
            
        if write_operation:
            return True
            
        for sp_abs in _SYS_PATH:
            if sp_abs:
                if sp_abs == _PROJECT_ROOT or sp_abs.startswith(_PROJECT_ROOT + _os.sep) or sp_abs.startswith(_PROJECT_ROOT.replace(_os.sep, '/')):
                    continue
                if sp_abs == _GEMINI_DIR or sp_abs.startswith(_GEMINI_DIR + _os.sep) or sp_abs.startswith(_GEMINI_DIR.replace(_os.sep, '/')):
                    continue
                if abs_p == sp_abs or abs_p.startswith(sp_abs + _os.sep) or abs_p.startswith(sp_abs.replace(_os.sep, '/')):
                    return False
        return False
    except Exception:
        return True
    finally:
        total_guard_time += (time.time() - t0)

# Guard builtins.open
_orig_open = _b.open
def _guarded_open(file, mode='r', *args, **kwargs):
    write_op = any(c in mode for c in ('w', 'a', '+', 'x')) if isinstance(mode, str) else False
    if _is_blocked_path(file, write_operation=write_op):
        raise PermissionError(f"Access to path '{file}' is restricted.")
    return _orig_open(file, mode, *args, **kwargs)
_b.open = _guarded_open

# Guard os.open
_orig_os_open = _os.open
_WRITE_FLAGS = getattr(_os, 'O_WRONLY', 0) | getattr(_os, 'O_RDWR', 0) | getattr(_os, 'O_CREAT', 0) | getattr(_os, 'O_APPEND', 0) | getattr(_os, 'O_TRUNC', 0) | getattr(_os, 'O_EXCL', 0)
def _guarded_os_open(path, flags, *args, **kwargs):
    write_op = bool(flags & _WRITE_FLAGS)
    if _is_blocked_path(path, write_operation=write_op):
        raise PermissionError(f"Access to path '{path}' is restricted.")
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
                raise PermissionError(f"Access to path '{check_path}' is restricted.")
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
                    raise PermissionError(f"Modification of path '{path}' is restricted.")
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
                    raise PermissionError(f"Modification of path '{src}' is restricted.")
            if dst is not None:
                if _is_blocked_path(dst, write_operation=True):
                    raise PermissionError(f"Modification of path '{dst}' is restricted.")
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
                raise PermissionError(f"Access to database path '{database}' is restricted.")
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
                raise PermissionError(f"Execution of os.{name} is restricted.")
            return _blocked
        setattr(_os, func_name, _make_blocked(func_name))

t_mat_start = time.time()
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as _plt
except Exception as e:
    print("Matplotlib failed:", e)
t_mat_end = time.time()

print(f"Matplotlib imported in {t_mat_end - t_mat_start}s")
print(f"Number of block checks: {call_count}")
print(f"Total time spent in block checks: {total_guard_time}s")
"""

import subprocess
t0 = time.time()
subprocess.run([sys.executable, "-I", "-c", script_code])
print(f"Total run time: {time.time() - t0}s")
