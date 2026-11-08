//! CLIPTORA Rust Core — filesystem inventory only (not an AI or FFmpeg replacement).
//! Emits one JSON object per video on stdout: {"path":"...","size":N,"mtime_ns":N}.
//! No source files are opened or modified; only filesystem metadata is read.
use std::env;
use std::fmt::Write as FmtWrite;
use std::fs;
use std::io::{self, BufWriter, Write};
use std::path::{Path, PathBuf};
use std::time::UNIX_EPOCH;

fn is_video(path: &Path) -> bool {
    matches!(
        path.extension()
            .and_then(|part| part.to_str())
            .map(|part| part.to_ascii_lowercase())
            .as_deref(),
        Some("mp4" | "mkv" | "mov" | "avi" | "webm" | "m4v" | "ts")
    )
}

fn json_string(value: &str) -> String {
    let mut out = String::with_capacity(value.len() + 2);
    for c in value.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c <= '\u{001f}' => {
                write!(out, "\\u{:04x}", u32::from(c)).expect("write to string");
            }
            _ => out.push(c),
        }
    }
    out
}

fn is_hidden_dir(name: &std::ffi::OsStr) -> bool {
    name.to_str().is_some_and(|s| s.starts_with('.'))
}

fn scan(root: &Path, output: &mut impl Write) -> io::Result<()> {
    if !root.is_dir() {
        return Err(io::Error::new(io::ErrorKind::NotFound, "source folder does not exist"));
    }
    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        // A transient inaccessible subdirectory should not break the whole scan.
        let entries = match fs::read_dir(&dir) {
            Ok(it) => it,
            Err(err) if dir == root => return Err(err),
            Err(_) => continue,
        };
        for entry in entries {
            let entry = match entry { Ok(entry) => entry, Err(_) => continue };
            let kind = match entry.file_type() { Ok(kind) => kind, Err(_) => continue };
            if kind.is_symlink() {
                continue;
            }
            let path = entry.path();
            if kind.is_dir() {
                if !is_hidden_dir(&entry.file_name()) {
                    stack.push(path);
                }
                continue;
            }
            if !kind.is_file() || !is_video(&path) {
                continue;
            }
            let info = match entry.metadata() { Ok(info) => info, Err(_) => continue };
            if info.len() == 0 { continue; }
            let modified = match info.modified() { Ok(value) => value, Err(_) => continue };
            let timestamp = match modified.duration_since(UNIX_EPOCH) {
                Ok(value) => value.as_nanos(),
                Err(_) => continue,
            };
            // Do not silently corrupt non-UTF8 paths. Python will be used if a
            // higher-level scan detects an unsupported or inconsistent result.
            let path = match path.to_str() { Some(path) => path, None => continue };
            writeln!(output, "{{\"path\":\"{}\",\"size\":{},\"mtime_ns\":{}}}",
                     json_string(path), info.len(), timestamp)?;
        }
    }
    output.flush()
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args_os();
    let _command = args.next();
    let path = args.next().ok_or("Usage: cliptora-scanner <source-directory>")?;
    if args.next().is_some() { return Err("One source directory is required".into()); }
    let user_path = PathBuf::from(path);
    let root = if user_path.is_absolute() { user_path }
               else { env::current_dir()?.join(user_path) };
    let stdout = io::stdout();
    let mut output = BufWriter::new(stdout.lock());
    scan(&root, &mut output)?;
    Ok(())
}

fn main() {
    if let Err(err) = run() {
        eprintln!("CLIPTORA scanner: {err}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn json_escapes_windows_paths_and_controls() {
        assert_eq!(json_string("C:\\foo\\bar\".mp4\n"), "C:\\\\foo\\\\bar\\\".mp4\\n");
        assert_eq!(json_string("\u{0001}"), "\\u0001");
    }

    #[test]
    fn extensions_are_case_insensitive() {
        assert!(is_video(Path::new("SESSION.MKV")));
        assert!(is_video(Path::new("episode.ts")));
        assert!(!is_video(Path::new("readme.txt")));
    }

    #[test]
    fn scan_skips_hidden_directories_zero_byte_files_and_finds_unicode() {
        let suffix = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let dir = env::temp_dir().join(format!("cliptora_rust_test_{}_{}", std::process::id(), suffix));
        fs::create_dir_all(dir.join(".cache")).unwrap();
        fs::create_dir_all(dir.join("recordings")).unwrap();
        fs::write(dir.join("recordings").join("игра.MP4"), b"1234").unwrap();
        fs::write(dir.join(".cache").join("ignore.mp4"), b"123").unwrap();
        fs::write(dir.join("recordings").join("zero.mp4"), b"").unwrap();
        let mut out = Vec::new();
        let result = scan(&dir, &mut out);
        let _ = fs::remove_dir_all(&dir);
        result.unwrap();
        let s = String::from_utf8(out).unwrap();
        assert!(s.contains("игра.MP4"));
        assert!(s.contains("\"size\":4"));
        assert_eq!(s.lines().count(), 1);
    }
}
