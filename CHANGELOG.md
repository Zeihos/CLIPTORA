# 0.1.12 Alpha — composed montage preview (2026-11-09)

- Add opt-in 480p MP4 preview of up to the **first 120 seconds** of the selected draft, in editor order. It uses the normal FFmpeg audio/video effects and zoom, with faster encoding.
- Provide a dedicated browser player with range-based seeking and stale-preview checks after edits or media changes.
- Keep cached previews in the project's `previews/` directory, never overwrite final exports or original footage, and clean up failed staging files.
- Disable playback when the configured normalization/fades differ from the rendered preview; require explicit regeneration.
- Add preview timeline planning, fingerprint, FFmpeg integration and HTTP streaming regression tests.

# 0.1.11 Alpha — export quality and failure safety (2026-11-09)

- Add opt-in per-clip FFmpeg loudness normalization targeting -16 LUFS / -1.5 dBTP. Warn that single-pass processing may amplify quiet backgrounds and is not whole-program measurement.
- Add optional 150/300 ms audio and video fade-through-black around cuts, without overlap or subtitle timeline shifts; shrink fades for very short clips. Existing hard cuts remain the default.
- Write MP4 into `.partial.mp4` and atomically rename on completed concat. Remove staging file if rendering fails and retain previous successful export pointer.
- Store export quality options in per-render JSON sidecar, and use collision-resistant output filenames.
- Add unit and FFmpeg integration regression tests; no new Python dependencies.

# 0.1.10 Alpha — reversible alternative plans (2026-11-09)

- Preview three heuristic edit selections (balanced, dialogue-heavy, action-heavy) without changing the current manual draft.
- Inspect proposed scenes in the local player before explicitly applying a plan.
- Every apply saves a previous draft in project.json (up to five undo levels), restoring labels, trims and disabled segments even after a restart.
- Reject stale previews after persistent project changes and block applying during analysis/export.
- These presets do not understand jokes or game events; 250 GB library performance has not been verified.

# 0.1.8 Alpha — dialogue context and natural endings

- Add a deterministic transcript-context planner. It keeps preceding setup lines, a ranked/reaction-adjacent sentence, its reply and an ending beat rather than simply adding a fixed 3 seconds around speech groups.
- Use existing Ollama `humor` scores (when configured) and corroborated audio peaks as **ranking hints**, not reliable joke or event recognition.
- Clamp proposed dialogue clips to 36 seconds and skip malformed/empty ASR segments. Keep far-apart scenes separate.
- Show context reasons alongside the original sound/motion selection reasons.
- Build new selections directly from saved 0.1.7 analysis: no reanalysis is required, but manually reviewed drafts must be backed up before using Create selection.
- Add regression checks for setup, payoff, response, reaction tails, boundaries, long dialogs and engine integration.

# 0.1.7 Alpha — explainable reaction highlights

- Find *relative* audio spikes compared with the preceding six seconds rather than simply selecting the loudest recording moments.
- Filter isolated single-bucket audio anomalies unless nearby speech or visual movement offers corroborating context.
- Optionally correlate reaction windows with Whisper timestamps and visual motion, and show human-readable selection reasons in the review UI.
- Increase dialogue highlight ranking when a nearby sound reaction supports the setup/payoff; keep three seconds of surrounding dialogue.
- Run on saved 0.1.6 analysis data: no new speech models, reanalysis, or cloud services are needed to try the updated selection algorithm.
- Add deterministic regression tests covering constant music, audio glitches, dialogue, motion, silence and media boundaries.
- Caution: audio bursts do not imply humor, a particular emotion, a game kill, or even a human voice; every suggestion needs review.

# 0.1.6 Alpha — durable analysis queue

- Persistent per-file analysis queue with `pending`, `running`, `complete` and `failed` states in local `project.json`.
- Restart recovery: interrupted files are returned to pending; completed video analysis is reused.
- Damaged video fails independently; remaining files keep processing. Clicking Analyze again retries incomplete files.
- Configurable 1–8 CPU threads (default 2) for FFmpeg and faster-whisper, sequential processing to limit peak RAM.
- Queue counters and per-file errors in the local browser UI.
- Source file safety check before analyzing, requiring a rescan if it changed.
- Keeps optional Rust scanner and existing v0.1.5 project files compatible.

# Changelog

## 0.1.9-alpha — 2026-11-08

- Add explainable quality ranking for dialogue context, a small penalty for isolated one-word shouts, and modest preference for setup + response.
- Filter near-identical informative transcript-based candidates across recordings, preserving distinct punchlines and nonverbal reactions.
- Keep clip decisions in original source order and preserve cached analysis, source media and existing drafts until a user explicitly rebuilds selection.
- Show adjusted selection priority, ranking hints and deduplication summary in the UI.
- Add regression tests for candidate comparisons, source overlaps, invalid scores and persisted selection summary.
- This remains lexical/heuristic ranking; no semantic video understanding or guaranteed comedic timing.

## 0.1.5-alpha — 2026-11-08

- Add optional no-dependency Rust Core metadata scanner for local video libraries.
- Automatically fall back to the existing Python scan when Rust is missing, fails, or outputs invalid metadata.
- Preserve existing media IDs, analysis cache and manual edits across Rust/Python backends, including older 0.1.4 project files.
- Add an opt-in Windows Rust build script and Rust+Python integration tests on Windows and Linux CI.
- Rust only enumerates files; FFmpeg/ffprobe, AI inference, clip editing and export remain in Python.
- No verified performance claims for a 250 GB library yet.

## 0.1.4-alpha — 2026-11-08

- Preserve media IDs, cached analysis and manually reviewed clips across rescans when source recordings are unchanged.
- Replace only the changed source entries and discard only references to changed or removed recordings.
- Reanalyze when speech/vision/Ollama settings change or when Whisper becomes available after installation.
- Skip repeat analysis when every source has a current cache signature.
- Add regression tests for rescan preservation, changed recordings and resumable analysis.
- Existing 0.1.3 analyzed files without a settings signature are safely treated as needing one analysis pass.

## 0.1.3-alpha — 2026-11-08

- Renamed the application to **CLIPTORA** in the browser UI, window title, launcher scripts and export filenames.
- Added project icon, GitHub banner, public documentation and source license.
- Preserved compatibility with existing Alpha projects stored in the former user data directory.
- Retained the Python **3.12** selection and binary-only `faster-whisper` installation introduced in 0.1.2.

## Earlier alpha history

- **0.1.2:** Windows launchers explicitly select Python 3.12 to avoid Python 3.15 / PyAV wheel build failures.
- **0.1.1:** Normalized Windows CMD scripts to CRLF and ASCII to fix broken batch execution.
- **0.1.0:** Initial local scanner, analysis, review UI and FFmpeg render pipeline.
