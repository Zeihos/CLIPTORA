# Contributing to CLIPTORA

Thanks for helping improve CLIPTORA. This is experimental local-first software.

- Open an issue for bugs, incorrect clip selection, problems with FFmpeg/Whisper, or a feature proposal.
- Do **not** upload original footage, recorded conversations, API keys or personal file paths in issues.
- Use Python 3.12. Prefer small changes with automated tests and readable error messages.
- Before submitting a PR run `python -m unittest discover -s tests -v` and `python -m py_compile engine.py server.py`.
- Keep the app localhost-only. Do not make cloud uploads a default or silently change user data directories.
- Document dependencies and their licenses when adding them. Prefer open-source local processing and explain optional networking clearly.
- PRs should include a short summary, steps to reproduce/test, and screenshots when UI changes are relevant.

See [SECURITY.md](SECURITY.md) for vulnerability reporting.
