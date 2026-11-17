"""Launch a real bundled Windows .exe and verify UI / Rust discovery.

Usage: python scripts/smoke_portable.py dist/CLIPTORA/CLIPTORA.exe
No source checkout, system Python or FFmpeg are needed by the child process.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def available_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def smoke(executable):
    exe = Path(executable).resolve()
    if not exe.is_file():
        raise FileNotFoundError(exe)
    port = available_port()
    with tempfile.TemporaryDirectory(prefix='cliptora-smoke-') as temp:
        output = Path(temp) / 'server.log'
        # Do not accidentally rely on installed Python or FFmpeg during startup.
        env = os.environ.copy()
        env.pop('CLIPTORA_SCANNER', None)
        with output.open('wb') as log:
            process = subprocess.Popen(
                [str(exe), '--no-browser', '--port', str(port), '--work-dir', str(Path(temp) / 'project')],
                cwd=temp, stdout=log, stderr=subprocess.STDOUT, env=env,
            )
            try:
                base = f'http://127.0.0.1:{port}'
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise AssertionError('CLIPTORA.exe exited before HTTP startup')
                    try:
                        with urlopen(base + '/api/status', timeout=2) as response:
                            status = json.load(response)
                        break
                    except (URLError, OSError, TimeoutError):
                        time.sleep(0.4)
                else:
                    raise AssertionError('Timed out waiting for CLIPTORA.exe HTTP server')
                assert 'files' in status and 'clips' in status, status
                assert status.get('rust_scanner_available') is True, 'Bundled Rust scanner not found'
                with urlopen(base + '/', timeout=5) as response:
                    page = response.read()
                    assert response.status == 200 and b'CLIPTORA' in page
                with urlopen(base + '/assets/cliptora-icon.svg', timeout=5) as response:
                    assert response.status == 200 and b'<svg' in response.read()
                print('EXE smoke test OK: API, UI, icon, Rust scanner')
            except Exception:
                log.flush()
                print(output.read_text(encoding='utf-8', errors='replace')[-6000:], file=sys.stderr)
                raise
            finally:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=8)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python scripts/smoke_portable.py path/to/CLIPTORA.exe')
    smoke(sys.argv[1])
