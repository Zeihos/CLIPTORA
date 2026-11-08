"""Optional Rust filesystem inventory for CLIPTORA; always usable without Rust.

The scanner returns metadata only. ffprobe, speech AI and FFmpeg remain in Python.
Its subprocess output is only trusted after a complete successful exit. If a
binary is missing, crashes or returns invalid data, Python enumerates the
entire library instead of persisting an incomplete inventory.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

VIDEO_EXTS = {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.m4v', '.ts'}


def locate_scanner():
    """Find the opt-in scanner executable (Windows builds are not in git)."""
    override = os.environ.get('CLIPTORA_SCANNER')
    if override:
        return override
    root = Path(__file__).resolve().parent
    exe = 'cliptora-scanner.exe' if os.name == 'nt' else 'cliptora-scanner'
    for candidate in (root / 'tools' / exe,
                      root / 'rust' / 'scanner' / 'target' / 'release' / exe,
                      root / 'rust' / 'scanner' / 'target' / 'debug' / exe):
        if candidate.is_file():
            return str(candidate)
    return None


def _scan_python(root, stop):
    items = []
    for dirpath, dirs, filenames in os.walk(root, followlinks=False):
        if stop.is_set():
            raise InterruptedError('Сканирование остановлено')
        # Do not enter hidden or symlinked directories; avoid recursive loops.
        dirs[:] = [name for name in dirs
                   if not name.startswith('.') and not (Path(dirpath) / name).is_symlink()]
        for name in filenames:
            if stop.is_set():
                raise InterruptedError('Сканирование остановлено')
            if Path(name).suffix.lower() not in VIDEO_EXTS:
                continue
            file = Path(dirpath) / name
            try:
                if file.is_symlink():
                    continue
                info = file.stat()
            except OSError:
                continue
            if info.st_size > 0 and file.is_file():
                items.append({'path': str(file), 'size': info.st_size, 'mtime_ns': info.st_mtime_ns})
    return items


def _scan_rust(root, stop, binary):
    """Read line-delimited JSON, never shell-execute paths or load video data."""
    items = []
    flags = 0x08000000 if os.name == 'nt' else 0
    child = subprocess.Popen([str(binary), str(root)], stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, encoding='utf-8', errors='strict',
                             creationflags=flags)
    try:
        for line in child.stdout:
            if stop.is_set():
                raise InterruptedError('Сканирование остановлено')
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError('Rust scanner: invalid record')
            path = Path(item.get('path', ''))
            size, mtime_ns = item.get('size'), item.get('mtime_ns')
            if (not path.is_absolute() or not path.is_relative_to(root) or
                    '..' in path.parts or path.suffix.lower() not in VIDEO_EXTS or
                    path.is_symlink() or not isinstance(size, int) or isinstance(size, bool) or
                    not isinstance(mtime_ns, int) or isinstance(mtime_ns, bool) or
                    size <= 0):
                raise ValueError('Rust scanner: malformed metadata record')
            items.append({'path': str(path), 'size': size, 'mtime_ns': mtime_ns})
        if stop.is_set():
            raise InterruptedError('Сканирование остановлено')
        code = child.wait(timeout=30)
        if code:
            error = child.stderr.read()[-350:]
            raise RuntimeError(f'Rust scanner code {code}: {error}')
        return items
    finally:
        if child.poll() is None:
            child.kill()
        child.wait()
        if child.stdout:
            child.stdout.close()
        if child.stderr:
            child.stderr.close()


def discover(root, stop, notify=None):
    """Return (metadata, backend), automatically falling back on Rust errors."""
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError('Папка с видео не найдена')
    if stop.is_set():
        raise InterruptedError('Сканирование остановлено')
    binary = locate_scanner()
    if binary:
        try:
            result = _scan_rust(root, stop, binary)
            if notify:
                notify(f'Rust Core: найдено {len(result)} видео по метаданным')
            return result, 'rust'
        except InterruptedError:
            raise
        except (OSError, UnicodeError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            if notify:
                notify('Rust Core недоступен (' + str(exc)[:130] + '). Переключаюсь на Python.')
    elif notify:
        notify('Rust Core не собран — сканирование через Python.')
    return _scan_python(root, stop), 'python'
