# -*- mode: python ; coding: utf-8 -*-
"""Portable Windows onedir build.

Default: lightweight Core, no speech packages.
Set CLIPTORA_WITH_AI=1 after installing requirements-portable-ai.txt to bundle
faster-whisper's Python/native libraries (not downloadable model weights).
FFmpeg/FFprobe remain external in both editions.
"""
import os
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
SCANNER = ROOT / 'rust' / 'scanner' / 'target' / 'release' / 'cliptora-scanner.exe'
if not SCANNER.is_file():
    raise FileNotFoundError('Build Rust Core first: cargo build --release --locked --manifest-path rust/scanner/Cargo.toml')

bundle_ai = os.environ.get('CLIPTORA_WITH_AI', '0') == '1'
extra_datas = [
    (str(ROOT / 'web' / 'index.html'), 'web'),
    (str(ROOT / 'assets' / 'cliptora-icon.svg'), 'assets'),
]
extra_binaries = [(str(SCANNER), 'tools')]
extra_hiddenimports = []
if bundle_ai:
    # Explicitly bundle package data, model tokenizer metadata, and the native
    # libraries used by faster-whisper (CTranslate2 + PyAV). PyInstaller's
    # static importer alone cannot detect every dynamic import/DLL.
    from PyInstaller.utils.hooks import collect_all
    for package in ('faster_whisper', 'ctranslate2', 'av', 'tokenizers', 'huggingface_hub'):
        data, binaries, hidden = collect_all(package)
        extra_datas.extend(data)
        extra_binaries.extend(binaries)
        extra_hiddenimports.extend(hidden)
    extra_hiddenimports.extend(['faster_whisper', 'ctranslate2', 'av', 'tokenizers', 'huggingface_hub'])

analysis = Analysis(
    [str(ROOT / 'server.py')],
    pathex=[str(ROOT)],
    binaries=extra_binaries,
    datas=extra_datas,
    hiddenimports=extra_hiddenimports,
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
