# Architecture

CLIPTORA is a local Python 3.12 application with a browser UI, not a cloud service or a standalone Windows installer.

```text
Original videos (read-only)
        |
scanner_bridge.py --- optional rust/scanner (file inventory only)
        |
engine.py --- FFprobe / FFmpeg --- audio and motion metadata
        |--- optional faster-whisper transcription
        |--- optional local Ollama dialogue hints
        |
highlight_signals.py / dialogue_context.py / climax_timing.py
        |
candidate_selection.py / plan_variants.py --- reviewable drafts
        |--- quality_benchmark.py (human reference intervals)
        |--- pacing.py / export_quality.py (non-destructive render settings)
        '--- montage_preview.py / engine.py --- MP4 and SRT
```

`server.py` provides the local UI and JSON endpoints at `127.0.0.1:8765`. `web/index.html` is served from disk. The server has no public-facing authentication: **do not expose its port to other networks**.

Project state is stored in a local `project.json` under `~/CLIPTORA` (or the existing legacy project directory); renders, cache and previews are stored separately from source video. Rescans reuse cached analysis for unchanged files. The processing queue saves completed files so a restart does not require reprocessing them. Rust is optional; ffprobe, decoding, inference and rendering remain in Python/FFmpeg.

Python modules remain at repository root for compatibility with existing launcher scripts and tests. Packaging as a Python library or shipping a `.exe` requires a separately tested migration.
