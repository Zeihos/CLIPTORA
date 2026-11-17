# -*- mode: python ; coding: utf-8 -*-
"""Reproducible onedir Windows build: pyinstaller --clean packaging/cliptora.spec.

Bundled: Python runtime, UI, CLIPTORA modules and native Rust scanner.
External: ffmpeg/ffprobe (system PATH or tools/ adjacent to CLIPTORA.exe).
Optional Whisper and Ollama models are not part of this experimental build.
"""
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent.parent
SCANNER = ROOT / 'rust' / 'scanner' / 'target' / 'release' / 'cliptora-scanner.exe'
if not SCANNER.is_file():
    raise FileNotFoundError('Build Rust Core first: cargo build --release --locked --manifest-path rust/scanner/Cargo.toml')

analysis = Analysis(
    [str(ROOT / 'server.py')],
    pathex=[str(ROOT)],
    binaries=[(str(SCANNER), 'tools')],
    datas=[
        (str(ROOT / 'web' / 'index.html'), 'web'),
        (str(ROOT / 'assets' / 'cliptora-icon.svg'), 'assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'test', 'unittest', 'pydoc'],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name='CLIPTORA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=str(ROOT / 'assets' / 'cliptora.ico'),
)
coll = COLLECT(exe, analysis.binaries, analysis.datas,
               strip=False, upx=False, name='CLIPTORA')
