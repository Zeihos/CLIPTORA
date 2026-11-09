<p align="center"><img src="assets/cliptora-banner.svg" alt="CLIPTORA — Local-first AI video editor" width="100%"></p>

<p align="center">
  <strong>CLIPTORA</strong> — a free, open-source, local-first video highlight editor for Windows.<br>
  Scan your footage, analyze speech and activity, review the best moments, and export a cut.
</p>

<p align="center">
  <img alt="Status: alpha" src="https://img.shields.io/badge/status-alpha-9485FF">
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB">
  <img alt="Windows" src="https://img.shields.io/badge/platform-Windows-384A6D">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-5CD7E6">
</p>

> [!IMPORTANT]
> **Alpha 0.1.11**. This is an experimental *first-cut/highlight selection* app, **not** a fully autonomous professional editor. It cannot reliably understand humor, game events, or comedic timing. Review selected clips before publishing. No 250 GB performance claim has been verified. Rust acceleration is opt-in and is limited to filesystem inventory.


### Предпросмотр готового монтажа (v0.1.12)

В разделе **Экспорт** после выбора сцен и параметров звука/переходов нажмите **«Собрать предпросмотр · первые 2 мин»**. CLIPTORA создаст отдельный MP4 в 480p в рабочей папке `previews/`, сохранив порядок сцен, обрезку, зум, нормализацию и затухания. Файл можно воспроизвести и перемотать в браузере.

- Режим ограничен **первыми 120 секундами** выбранного черновика. Длинный монтаж целиком формируется обычным экспортом.
- Предпросмотр **не меняет** исходные записи, ручной монтаж, субтитры и `last_output`. Встраивание субтитров не предусмотрено.
- Если изменить границы, набор клипов или настройки звука/переходов, предпросмотр станет устаревшим — создайте новый.
- Для работы необходим FFmpeg; предпросмотр требует кодирования и не является рендерингом в реальном времени.

## What it can do today

| Area | Supported in the alpha |
| --- | --- |
| Library | Recursively scan a user-selected folder of videos |
| Analysis | Relative audio reaction peaks and optional visual motion; optional local speech recognition via `faster-whisper` |
| Context | Keep surrounding dialogue, rank candidates by reviewable context signals and manually edit clip start/end |
| AI | Optional **local** Ollama for scoring dialogue (quality is experimental) |
| Review | Browser preview, human-readable selection reasons, enable/disable, adjust clips and mark subtle zooms |
| Export | FFmpeg MP4 at 480p / 720p / 1080p and transcript-derived SRT; optional per-clip loudness normalization and short fade-through-black transitions |
| Processing | Localhost server; preserves source files; incremental rescans, stable media IDs and resumable per-file analysis |
| Queue | Persisted per-video progress; resume after restart; file-level errors and retry |
| Resource controls | Sequential video analysis and adjustable FFmpeg/Whisper CPU threads (1–8; default 2) |
| Rust Core | Optional Rust video file inventory scanner with automatic Python fallback (Rust does **not** run speech AI or FFmpeg) |

**Not yet implemented:** automatic meme selection, precise semantic scene understanding, motion tracking, elaborate keyframed effects, professional audio mixing, a standalone `.exe` installer, or a multi-track timeline.

## Quick start — Windows

1. Install **Python 3.12** (not 3.15). The Windows launchers explicitly select 3.12.
2. Unzip this repository somewhere outside your footage directory.
3. Run `SETUP_WINDOWS.bat` to check Python and FFmpeg (the script can install FFmpeg with `winget`).
4. Optional: run `INSTALL_AI_WINDOWS.bat` for `faster-whisper` speech recognition. Skip if already installed under Python 3.12.
5. Run `START_WINDOWS.bat`; open <http://127.0.0.1:8765> if the browser does not start.
6. **Optional Rust Core:** install the stable Rust toolchain using [rustup](https://rustup.rs/) and run `BUILD_RUST_WINDOWS.bat`. This builds a native scanner into `tools/cliptora-scanner.exe`. It is not needed for basic operation.
7. Select the source footage folder → **Scan** → **Analyze** → **Create selection** → review clips → **Export MP4**.

Since v0.1.6, analysis progress is saved after each file in `project.json`. If the app closes or Windows restarts, re-open the app and click **Analyze / Continue**; completed files are skipped. Failed videos remain visible and can be retried. CPU threads can be limited to avoid saturating your computer; this does **not** cap all OS memory usage.

Since v0.1.4, rescanning an unchanged folder keeps previously selected clips and their edits. Changed or removed source files invalidate only their own clips; changed AI settings trigger reanalysis. Files analyzed before v0.1.4 will require one cache refresh because the old version did not record analysis settings.

The first Whisper transcription may download model weights from the Internet. Afterwards the model can run locally. For dialogue scoring you can optionally install [Ollama](https://ollama.com/) and download a model; it is **not required**.

Read [УСТАНОВКА.txt](УСТАНОВКА.txt) for Russian instructions.

### Manual server start

```powershell
py -3.12 server.py
```

This script uses Python's standard-library HTTP server and binds to `127.0.0.1` only. `FFmpeg` and `ffprobe` must be on PATH (or in `tools/`).

## Rust Core (optional)

The Rust scanner is an independent, dependency-free binary located at `rust/scanner/`.
It walks the chosen footage directory and returns only video paths, sizes and modification times in JSON-lines format. It does **not** decode footage, replace FFmpeg, or accelerate Whisper. For new/changed video files, `ffprobe` still dominates scan time on many setups.

```powershell
cargo test --manifest-path rust/scanner/Cargo.toml
cargo build --release --locked --manifest-path rust/scanner/Cargo.toml
```

On Windows use `BUILD_RUST_WINDOWS.bat` to copy the compiled binary to `tools/`. If the binary is unavailable or crashes, CLIPTORA automatically uses Python and keeps all existing library state. `CLIPTORA_SCANNER` can override the executable path. Never set it to an untrusted binary. Rust is optional for contributors as well as users.

## Privacy, storage and migration

- Sources are read in place and never intentionally overwritten or deleted.
- New project state and exports are under `%USERPROFILE%\CLIPTORA\` (`project.json`, `renders/`, `cache/`).
- If you already have a project from **Zeihos AI Montage Studio** and the new CLIPTORA data folder does not contain a project, CLIPTORA keeps using the legacy data directory to avoid copying large caches and breaking existing project paths.
- By default, **no footage is uploaded to a cloud service**. Whisper weights may download once, and Ollama is expected on `127.0.0.1`. Do not expose port 8765 to public networks.
- Do not commit footage, exported videos, the local project database or model files to GitHub.

## Roadmap

- [x] Local scan, audio analysis, review and MP4 export
- [x] Optional speech transcription, optional Ollama dialogue scoring
- [x] Windows launchers with explicit Python 3.12
- [ ] Stronger game-event and joke-context detection
- [x] Text-based near-duplicate shortlist filtering and transparent ranking hints
- [ ] Side-by-side visual clip comparison and event-aware semantic ranking
- [ ] Better zooms, captions, SFX and meme templates
- [x] Optional Rust file inventory with automatic Python fallback
- [ ] Long-library benchmarks and fault-tolerant job queue
- [ ] Real desktop packaging, GPU acceleration and hardware detection
- [ ] Multitrack non-linear editing timeline

See [CHANGELOG.md](CHANGELOG.md). This roadmap describes **plans**, not shipped features.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). For security concerns, see [SECURITY.md](SECURITY.md). Project code is released under the [MIT License](LICENSE); installed third-party software and models have their own licenses.

**Project:** CLIPTORA · **Maintainer:** [Zeihos](https://github.com/Zeihos) · **Version:** 0.1.11-alpha.

## Compare three edit drafts safely (v0.1.10)

After processing your videos, choose **Compare 3 variants** under Draft editing. CLIPTORA builds balanced, dialogue and action options from cached audio, speech and movement analysis. Preview does not overwrite project.json or manually edited clips; inspect any proposed shot in the local player.

Only an explicit Apply action replaces a draft. Previous clip lists (including enabled state, labels and trims) are recorded in plan_history in project.json, retaining up to five replacements. Choose Undo apply to restore the previous version even after restarting. Previews become invalid after changing the project. The legacy /api/plan endpoint also makes a reversible snapshot.

Presets change transparent heuristic rankings, not any AI understanding of jokes or events. Back up the workspace before major edits. Performance on a complete 250 GB library has not been verified.


## CLIPTORA 0.1.6 queue troubleshooting

- Stopping or closing the application during a video does not keep partial transcription for that video; it is processed from the start on resume. Completed **other** videos remain finished.
- A failed video is marked as failed. Other recordings still process. Press **Analyze / Continue** to retry failed files.
- If a file was modified since scanning, rescan the footage directory before retrying analysis.
- Thread control applies to FFmpeg decoding/filters and Whisper CPU inference; it cannot guarantee a fixed memory or CPU percentage. Queue runs one recording at a time.
- Project metadata and queue are stored locally in `project.json`. Keep a backup of it when editing a large library.

## CLIPTORA 0.1.7 — audio reaction highlights

Use the existing workflow **Scan → Analyze → Create selection**. For already-analyzed unchanged files, click **Create selection** again to rebuild the proposed clips using the new relative-reaction algorithm. This action replaces the draft selection, so **back up or export any manually reviewed draft first**. Simply upgrading does not destroy saved clip edits.

Each automatically suggested clip may include **Основание** (why it was suggested): sound spike compared to nearby sound, nearby speech and/or motion. These are statistical clues, **not** verified jokes, emotions, speakers or game events. The ``score/100`` is a ranking heuristic, not a calibrated probability.

The new detector only uses existing 0.5-second RMS levels and optional speech/motion metadata; it never sends gameplay recordings to an external service. A first scan and speech analysis can still take time. Audio-only videos work without Whisper or Rust.

## CLIPTORA 0.1.8 — speech context windows

The **Create selection** action now proposes bounded dialogue windows (at most 36 seconds) which try to preserve an earlier setup, a plausible punchline/reaction and a short follow-up/beat. Signals come from existing Whisper transcript timestamps, optional local Ollama heuristic ratings and the previously recorded audio-reaction metadata; the app **cannot reliably identify actual jokes or speakers**. Results remain reviewable, editable suggestions, not guaranteed funny clips.

The new context algorithm reuses cached analysis from 0.1.7: **you do not need to rescan or retranscribe** an unchanged recording. **Creating a new selection replaces the entire current draft** (including manually reviewed clips), so keep a backup of `project.json` or export your draft first. Just upgrading preserves the project without rewriting the draft.

## CLIPTORA 0.1.9 — shortlist quality and dialogue comparison

After the existing **Scan → Analyze** steps, press **Create selection** to rebuild a shortlist with the new local ranking stage. This version reuses existing analysis (Whisper / audio / motion) and adds no model downloads. It gives a small preference to extended dialogue with an earlier setup and later reply, and penalizes very short dialogue with little context. It suppresses near-identical, informative transcript passages when duration is comparable; generic labels like "sound reaction" never cause deduplication. Different punchlines are intentionally retained unless their text is extremely similar.

The interface now shows the original raw heuristic score through the ranking badge tooltip, the adjusted selection priority, the reasons for its adjustment and a summary of overlaps / duplicate suggestions skipped during the selection pass. **These signals do not prove that two clips contain the same visual event, or that a joke is funny.** If auto-transcription repeats or changes words, some repeated scenes may still pass or distinct dialogue may be filtered. Please review before exporting.

The `selection_summary` in local `project.json` describes the **last automatic shortlist** only. Subsequent manual clip edits do not recompute this history. Rebuilding the draft replaces previous manual edits as in earlier versions; make a backup or export before pressing Create selection again. Upgrading the application itself does not rebuild the draft or discard cached analysis.

## Export quality controls (v0.1.11)

Under **Export**, optional **Normalize volume** runs FFmpeg's single-pass `loudnorm=I=-16:TP=-1.5:LRA=11` on each selected scene independently, followed by 48 kHz stereo resampling. This is an approximation, not guaranteed integrated loudness across a complete finished movie; very quiet clips may have background noise amplified. Leave it off when you prefer original dynamics. The program never modifies the source recordings.

**Scene joins** can use hard cuts (default) or 150/300 ms **fade through black**. This is *not* an overlapping crossfade. Every segment retains its duration, so subtitle timestamps and montage timing do not change. Very short segments receive proportionally shorter fades to avoid all-black clips. Hard cuts are usually better for fast comedic/action pacing.

The MP4 is first written to a hidden `.partial.mp4` in the render directory, and published as a final `.mp4` only when FFmpeg successfully finishes concatenating the scene files. A failed export cleans its temporary files and does not overwrite `last_output` or previous completed renders. Each render uses a microsecond timestamp to avoid accidental filename collisions. Export options are recorded in the sidecar JSON manifest. These safeguards do not ensure successful subtitle burn-in in all cases; a separate SRT remains available.
