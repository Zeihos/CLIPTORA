@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
echo ============================================
echo    CLIPTORA - BUILD RUST SCANNER
echo ============================================
where cargo >nul 2>&1
if errorlevel 1 goto missing
cargo build --release --locked --manifest-path "rust\scanner\Cargo.toml"
if errorlevel 1 goto failed
if not exist "tools" mkdir "tools"
copy /Y "rust\scanner\target\release\cliptora-scanner.exe" "tools\cliptora-scanner.exe" >nul
if errorlevel 1 goto failed
echo [OK] Rust scanner built in tools\cliptora-scanner.exe
echo [INFO] Run START_WINDOWS.bat. Python fallback remains available.
pause
exit /b 0
:missing
echo [HELP] Rust toolchain is optional. Install from https://rustup.rs/
echo [HELP] The program works via Python without Rust.
pause
exit /b 1
:failed
echo [ERROR] Build failed. Python scanner will be used as a fallback.
pause
exit /b 1
