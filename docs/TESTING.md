# Testing and contributing

Use Python **3.12** for parity with the Windows scripts. Tests use the Python standard library; certain FFmpeg integration tests skip if FFmpeg/FFprobe are unavailable.

```sh
python -m compileall -q .
python -m unittest discover -s tests -v
```

Optional native scanner (requires Rust):

```sh
cargo test --locked --manifest-path rust/scanner/Cargo.toml
cargo build --release --locked --manifest-path rust/scanner/Cargo.toml
```

The GitHub Actions workflow tests both Windows and Ubuntu. It builds Rust and verifies the Python bridge can find the native binary. A skipped local Rust test **does not** prove native scanner parity.

Before publishing, manually scan a short sample of gameplay footage, review/edit a draft, apply/undo an alternate selection, render a preview, change a clip to invalidate that preview, then export and play back an MP4. Inspect the output and make sure the source footage is unchanged. Do not claim a 250 GB stress test, browser E2E test or release installer is complete unless it has actually been run.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for pull request guidelines. Never include actual recordings, transcripts, local project metadata or secrets in issue reports.
