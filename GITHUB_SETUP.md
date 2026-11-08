# GitHub publication checklist

**Repository name:** `CLIPTORA`

**Target:** `https://github.com/Zeihos/CLIPTORA`

**Visibility:** Public

**Description:** `CLIPTORA — free, local-first AI video editor for gaming highlights. FFmpeg + Whisper + optional Ollama. Open source.`

**Topics:** `video-editor`, `ai-video-editor`, `video-editing`, `open-source`, `ffmpeg`, `whisper`, `ollama`, `python`, `windows`, `gaming`, `highlights`

**Website:** None yet — don't invent a homepage URL.

**License:** MIT (included in `LICENSE`).

## Publish with GitHub CLI on Windows

1. Install [Git](https://git-scm.com/download/win) and [GitHub CLI](https://cli.github.com/).
2. Open a terminal in this folder and run `gh auth login`.
3. Run `PUBLISH_GITHUB_WINDOWS.bat`, which creates the public repository if it does not exist and publishes the tracked source files.
4. Open the GitHub repository to verify `README.md`, license, the Actions tab and publicity.
5. In repository **About**, use the description and topics above. Pin the repository to your profile if desired.

### If you prefer GitHub website

Create an **empty** public repository `CLIPTORA` under account `Zeihos` (do **not** auto-generate a README, license or `.gitignore`: they're included in this archive). Then run `PUBLISH_GITHUB_WINDOWS.bat` after `gh auth login`.

This repository is *source code*, not a signed Windows executable. GitHub releases can be added after packaging and Windows testing.
