# Changelog

## 0.1.3-alpha — 2026-11-08

- Renamed the application to **CLIPTORA** in the browser UI, window title, launcher scripts and export filenames.
- Added project icon, GitHub banner, public documentation and source license.
- Preserved compatibility with existing Alpha projects stored in the former user data directory.
- Retained the Python **3.12** selection and binary-only `faster-whisper` installation introduced in 0.1.2.

## Earlier alpha history

- **0.1.2:** Windows launchers explicitly select Python 3.12 to avoid Python 3.15 / PyAV wheel build failures.
- **0.1.1:** Normalized Windows CMD scripts to CRLF and ASCII to fix broken batch execution.
- **0.1.0:** Initial local scanner, analysis, review UI and FFmpeg render pipeline.
